# SODEX STABILITY NOTES:
# 1. NONCE SYNC: clOrdID must contain same timestamp as X-API-Nonce.
# 2. KEY ORDER: Must use OrderedDict with sequence: clOrdID, modifier, side, type, timeInForce, [price], quantity, reduceOnly, positionSide.
# 3. MODIFIERS: Normal=1, Bracket(Parent)=3, AttachedStop(TP/SL)=4.
# 4. MARKET: Omit 'price' to avoid IOC slippage cancellation.

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import time
import os
import json
import sqlite3
from typing import Optional
from contextlib import asynccontextmanager

from config import Config
from sdk.auth import SodexAuth

# Globals (Initialized inside lifespan or lazily)
db = None
client = None
news_agg = None
strategy = None
auto_bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, client, news_agg, strategy, auto_bot
    print("\n" + "="*50)
    print("SODEX AI BACKEND STARTING...")
    print("="*50)
    
    try:
        # ... existing imports ...
        from sdk.database import DatabaseManager
        from sdk.client import SodexClient
        from agents.news_aggregator import NewsAggregator
        from agents.strategy_engine import StrategyEngine
        from sdk.autonomous_bot import AutonomousBot

        print("[1/5] Initializing Database...")
        db = DatabaseManager()
        
        print("[2/5] Initializing SoDEX Client...")
        client = SodexClient(is_spot=False)
        
        print("[3/5] Initializing News Aggregator...")
        news_agg = NewsAggregator()
        
        print("[4/5] Initializing Strategy Engine...")
        strategy = StrategyEngine(db=db)
        
        print("[5/5] Initializing Autonomous Bot...")
        auto_bot = AutonomousBot(db)
        
        # Start bot loop and store the task
        print(">>> Starting Autonomous Loop in Background...")
        bot_task = asyncio.create_task(auto_bot.start_loop())
        
        print("="*50)
        print("BACKEND READY AT http://0.0.0.0:8000")
        print("="*50 + "\n")
        
        yield
        
        print("Shutting down...")
        if auto_bot: 
            auto_bot.stop()
        if bot_task:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        print(f"FATAL STARTUP ERROR: {e}")
        raise e

app = FastAPI(title="SoDEX AI Microservice", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def retry_async(func, *args, retries=3, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1: raise e
            await asyncio.sleep(delay)

class ExecuteRequest(BaseModel):
    payload: dict
    signature: str
    nonce: Optional[int] = None

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/api/analyze")
async def analyze_market(symbol: str = Query(..., description="The trading symbol")):
    try:
        price_str = await retry_async(client.get_mark_price, symbol)
        if not price_str:
            raise HTTPException(status_code=404, detail="Price not found")

        klines = await retry_async(client.get_klines, symbol, interval="15m", limit=20)
        news = await retry_async(news_agg.fetch_latest_news, symbol.split("-")[0])
        news_text = "\n".join([f"- {n['title']}" for n in news]) if news else ""

        analysis_result = strategy.ensemble_analyze(symbol, price_str, "OPEN", news_text, klines)

        return {
            "symbol": symbol,
            "current_price": price_str,
            "analysis": analysis_result,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/chart/klines")
async def get_market_klines(symbol: str, interval: str = "15m", limit: int = 100):
    klines = client.get_klines(symbol, interval, limit)
    return {"klines": klines}

@app.get("/api/markets")
async def get_available_markets():
    markets = client.get_markets()
    return {"markets": markets}

@app.get("/api/settings")
def get_settings(address: Optional[str] = Query(None)):
    if address == "undefined": address = None
    conf = db.get_config(address) if db else {}
    return {
        "is_active": conf.get("is_active", 0),
        "private_key": conf.get("private_key", ""),
        "symbol": conf.get("symbol", Config.TARGET_SYMBOL),
        "account_id": conf.get("account_id", Config.SODEX_ACCOUNT_ID)
    }

@app.post("/api/settings/save")
async def save_settings(req: Request):
    data = await req.json()
    address = data.get("address")
    pk = data.get("private_key")
    aid = data.get("account_id")
    sym = data.get("symbol", Config.TARGET_SYMBOL)
    lev = data.get("leverage", Config.DEFAULT_LEVERAGE)
    
    if not address or not pk:
        return {"code": -1, "error": "Address and Private Key are mandatory"}
    
    if db:
        db.save_config(address, pk, aid, sym, lev)
    return {"status": "success"}

@app.post("/api/settings/toggle")
def toggle_auto_trading(address: str, active: bool):
    if db: db.toggle_bot_active(address, active)
    return {"status": "success", "is_active": active}

@app.get("/api/stats")
async def get_stats(address: str = Query(None)):
    conf = None
    try:
        if not db: return {"stats": {}, "positions": [], "logs": []}
        
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Get basic stats
        stats = {}
        cursor.execute("SELECT * FROM bot_stats WHERE id = 1")
        row = cursor.fetchone()
        if row: stats = dict(row)
        
        # 2. Fetch real-time positions from SoDEX if address is provided
        live_positions = []
        if address and address != "undefined":
            try:
                # 0. Get user config from DB
                conf = db.get_config(address)
                
                pos_resp = await retry_async(client.get_perps_positions, address, conf.get("account_id") if conf else Config.SODEX_ACCOUNT_ID)
                print(f"DEBUG POS_RESP: {pos_resp}")
                if pos_resp and pos_resp.get("code") == 0:
                    data_body = pos_resp.get("data", {})
                    # Handle both formats: list directly in data OR nested positions list
                    if isinstance(data_body, list):
                        raw_positions = data_body
                    else:
                        raw_positions = data_body.get("positions", [])
                    
                    if isinstance(raw_positions, list):
                        # Use account_id from DB if available, else fallback
                        acc_id = conf.get("account_id") if conf else Config.SODEX_ACCOUNT_ID
                        # Fetch open orders to find TP/SL
                        orders_resp = await retry_async(client.get_perps_orders, address, acc_id)
                        raw_orders = orders_resp.get("data", {}).get("orders", []) if orders_resp else []
                        
                        # Debug: Print raw orders to see structure
                        if raw_orders:
                            print(f"DEBUG OPEN_ORDERS ({len(raw_orders)} found): {json.dumps(raw_orders[0], indent=2)}")
                        
                        for p in raw_positions:
                            # 1. Map Raw Keys to Standard Names
                            sym = p.get("symbol") or p.get("s")
                            raw_entry = p.get("avgEntryPrice") or p.get("ep") or "0"
                            entry = float(raw_entry)
                            size = float(p.get("size") or p.get("sz") or 0)
                            leverage = p.get("leverage") or p.get("l") or 10
                            
                            # 2. Fetch Real-time Mark Price
                            try:
                                mark_val = await retry_async(client.get_mark_price, sym)
                                mark = float(mark_val) if mark_val else entry
                            except:
                                mark = entry
                            
                            # 3. Handle PnL
                            api_upnl = p.get("unrealizedPnL") or p.get("upnl") or p.get("pnl")
                            try:
                                if api_upnl is not None and str(api_upnl).strip() != "":
                                    unrealized = float(api_upnl)
                                else:
                                    unrealized = (mark - entry) * size if entry > 0 else 0
                            except:
                                unrealized = 0.0
                            
                            # 4. Find TP/SL in open orders
                            tp_val = "---"
                            sl_val = "---"
                            for o in raw_orders:
                                # Match symbol
                                o_sym = o.get("symbol") or o.get("s")
                                if o_sym == sym:
                                    # Identify by stopPrice presence and stopType
                                    sp = o.get("stopPrice") or o.get("sp")
                                    if sp:
                                        st = o.get("stopType") or o.get("st")
                                        # Handle both string (TAKE_PROFIT) and integer (2) formats
                                        if st == 2 or st == "TAKE_PROFIT": 
                                            tp_val = str(sp)
                                        elif st == 1 or st == "STOP_LOSS": 
                                            sl_val = str(sp)
                            
                            live_positions.append({
                                "symbol": sym,
                                "side": "LONG" if size > 0 else "SHORT",
                                "size": abs(size),
                                "leverage": leverage,
                                "entry_price": str(raw_entry),
                                "mark_price": str(mark),
                                "unrealized_pnl": str(round(unrealized, 4)),
                                "margin": p.get("initialMargin") or p.get("im") or "0",
                                "tp_price": tp_val,
                                "sl_price": sl_val
                            })
                    
                    stats["positions"] = live_positions
            except Exception as pe:
                print(f"Positions fetch error ({type(pe).__name__}): {pe}")
        
        # 3. Fallback to DB if no live positions found
        if not live_positions:
            cursor.execute("SELECT * FROM active_position WHERE id = 1")
            pos = cursor.fetchone()
            if pos:
                live_positions.append(dict(pos))
        
        # 4. Get logs
        cursor.execute("SELECT * FROM bot_logs ORDER BY id DESC LIMIT 10")
        logs = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return {"stats": stats, "positions": live_positions, "logs": logs}
        
    except Exception as e:
        print(f"GENERAL STATS ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"stats": {}, "positions": [], "logs": [], "error": str(e)}

@app.post("/api/execute")
async def execute_trade(req: ExecuteRequest):
    result = await retry_async(client.execute_order, req.payload, req.signature, req.nonce)
    return result

@app.post("/api/leverage")
async def update_leverage(req: ExecuteRequest):
    result = await retry_async(client.execute_leverage, req.payload, req.signature, req.nonce)
    return result

class UnifiedTradeRequest(BaseModel):
    address: str
    account_id: int
    symbol: str
    side: int # 1=BUY, 2=SELL
    order_type: int # 1=LIMIT, 2=MARKET
    quantity: str
    price: str
    leverage: int
    margin_mode: int = 2 # Default CROSS
    tp_price: Optional[str] = None
    sl_price: Optional[str] = None

@app.post("/api/trade-unified")
async def trade_unified(req: UnifiedTradeRequest):
    try:
        # Step 1: Prep Leverage Payload
        from collections import OrderedDict
        symbol_id = 1 if req.symbol == "BTC-USD" else 2
        
        # FETCH Private Key from DB for this specific user
        conf = db.get_config(req.address) if db else {}
        signing_key = conf.get("private_key")
        
        if not signing_key:
            return {"code": -1, "error": "Private Key not found for this wallet. Please save it in settings first."}

        lev_params = OrderedDict([
            ("accountID",  int(req.account_id)),
            ("symbolID",   int(symbol_id)),
            ("leverage",   int(req.leverage)),
            ("marginMode", int(req.margin_mode))
        ])
        
        # Step 2: Sign & Hit Leverage
        print(f">>> UNIFIED: Step 1 - Syncing Leverage to x{req.leverage}")
        nonce_lev = int(time.time() * 1000)
        sig_lev = SodexAuth.create_signature(
            private_key=signing_key,
            method="updateLeverage", # Correct method name
            params=lev_params,
            api_name=client.api_key_name,
            api_nonce=nonce_lev,
            chain_id=Config.SODEX_CHAIN_ID,
            api_public_key=client.api_public_key
        )
        
        lev_res = await retry_async(client.execute_leverage, lev_params, sig_lev, nonce_lev)
        if lev_res.get("code") != 0:
            return {"code": -1, "error": f"Leverage Sync Failed: {lev_res.get('error') or lev_res.get('msg')}"}

        # Step 3: Prep Order Payload
        print(f">>> UNIFIED: Step 2 - Executing {req.symbol} Order")
        from collections import OrderedDict
        # Step 4: Sign & Hit Order
        nonce_ord = int(time.time() * 1000) + 1 # Ensure unique nonce
        cl_ord_id = f"{req.account_id}-{nonce_ord}"
        
        # Use the signing_key fetched from DB above

        # Build order item based on type
        is_market = int(req.order_type) == 2
        has_bracket = bool(req.tp_price or req.sl_price)
        
        # Order of keys is CRITICAL for SoDEX signature
        order_item = OrderedDict()
        order_item["clOrdID"] = str(cl_ord_id)
        order_item["modifier"] = 3 if has_bracket else 1
        order_item["side"] = int(req.side)
        order_item["type"] = int(req.order_type)
        order_item["timeInForce"] = 3 if is_market else 1
        
        if not is_market:
            order_item["price"] = str(req.price)
            
        order_item["quantity"] = str(req.quantity)
        order_item["reduceOnly"] = False
        order_item["positionSide"] = 1

        orders_list = [order_item]

        # Add TP/SL Orders if provided
        if req.tp_price:
            orders_list.append(OrderedDict([
                ("clOrdID",      f"{cl_ord_id}-tp"),
                ("modifier",     4), # ATTACHED_STOP
                ("side",         2 if int(req.side) == 1 else 1),
                ("type",         2), # MARKET
                ("timeInForce",  3),
                ("quantity",     str(req.quantity)),
                ("stopPrice",    str(req.tp_price)),
                ("stopType",     2),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))
        
        if req.sl_price:
            orders_list.append(OrderedDict([
                ("clOrdID",      f"{cl_ord_id}-sl"),
                ("modifier",     4), # STOP_LOSS
                ("side",         2 if int(req.side) == 1 else 1),
                ("type",         2), # MARKET
                ("timeInForce",  3),
                ("quantity",     str(req.quantity)),
                ("stopPrice",    str(req.sl_price)),
                ("stopType",     1),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))

        params = OrderedDict([
            ("accountID", int(req.account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders",    orders_list)
        ])

        sig_ord = SodexAuth.create_signature(
            private_key=signing_key,
            method="newOrder",
            params=params,
            api_name=client.api_key_name,
            api_nonce=nonce_ord,
            chain_id=Config.SODEX_CHAIN_ID,
            api_public_key=client.api_public_key
        )
        
        order_res = await retry_async(client.execute_order, params, sig_ord, nonce_ord)
        return order_res

    except Exception as e:
        return {"code": -1, "error": str(e)}

@app.get("/api/check-account")
async def check_account(address: str = Query(...)):
    try:
        # 1. Get Account ID from State
        state = await retry_async(client.get_perps_state, address)
        aid = None
        if state and state.get("code") == 0:
            aid = state.get("data", {}).get("aid")

        # 2. Get Balance from Balances endpoint
        bal_resp = await retry_async(client.get_perps_balances, address)
        balance = "0.00"
        if bal_resp and "data" in bal_resp:
            # Assuming first coin or vUSDC
            balances = bal_resp["data"].get("balances", [])
            if balances:
                balance = balances[0].get("total", "0.00")

        return {
            "registered": aid is not None,
            "account_id": aid,
            "balance": balance,
            "address": address
        }
    except Exception as e:
        return {"registered": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
