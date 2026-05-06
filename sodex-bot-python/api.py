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
from sdk.client import SodexClient
from sdk.database import DatabaseManager

# Globals (Initialized inside lifespan or lazily)
db = None
client = None
news_agg = None
strategy = None
auto_bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, client, news_agg, strategy, auto_bot, market_intel
    print("\n" + "="*50)
    print("SODEX AI BACKEND STARTING...")
    print("="*50)
    
    try:
        # Initializing Managers
        from agents.news_aggregator import NewsAggregator
        from agents.strategy_engine import StrategyEngine
        from sdk.autonomous_bot import AutonomousBot
        from agents.market_intelligence import MarketIntelligence

        print("[1/5] Initializing Database...")
        db = DatabaseManager()
        
        print("[2/5] Initializing SoDEX Client...")
        client = SodexClient(is_spot=False)
        
        print("[3/5] Initializing News Aggregator...")
        news_agg = NewsAggregator()

        print("[3.5/5] Initializing Market Intelligence...")
        market_intel = MarketIntelligence()
        
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

@app.get("/api/market-intelligence")
async def get_market_intel(symbol: str = "BTC"):
    global market_intel
    if not market_intel:
        return {"error": "Market Intel not initialized"}
    
    # Simple symbol mapping for ETF (e.g. BTC-USD -> BTC)
    clean_symbol = symbol.split("-")[0]
    return market_intel.get_comprehensive_intel(clean_symbol)

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
            return await asyncio.to_thread(func, *args, **kwargs)
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
async def analyze_market(
    symbol: str = Query(..., description="The trading symbol"),
    risk: str = Query("SAFETY", description="Risk profile: SAFETY, MODERATE, AGGRESSIVE"),
    balance: str = Query("100", description="Current account balance in vUSDC"),
    address: Optional[str] = Query(None, description="The user wallet address"),
    mode: Optional[str] = Query(None, description="The selected trading mode")
):
    risk_profile = risk
    try:
        price_str = await retry_async(client.get_mark_price, symbol)
        if not price_str:
            raise HTTPException(status_code=404, detail="Price not found")

        klines = await retry_async(client.get_klines, symbol, interval="15m", limit=50)
        # Normalize symbol for news (e.g., BTC-USD -> BTC)
        news_sym = symbol.split("-")[0]
        news = news_agg.fetch_latest_news(news_sym, limit=20)
        news_text = "\n".join([f"- {n['title']}" for n in news]) if news else ""

        # Fetch Market Intelligence
        intel_data = market_intel.get_comprehensive_intel(symbol.split("-")[0])

        # 6. Analyze with Strategy V2
        from agents.strategy_v2 import StrategyV2
        strategy_v2 = StrategyV2()
        
        # Priority: 1. Mode from URL param, 2. Mode from DB, 3. Default MOMENTUM
        user_conf = db.get_config(address) if (address and db) else None
        
        # If mode is passed in URL, use it (Real-time dashboard selection)
        # Otherwise use from DB
        final_mode = mode or (user_conf["trading_mode"] if (user_conf and "trading_mode" in user_conf.keys()) else "MOMENTUM")
        
        # Auto-persist chosen mode to DB so it survives refresh
        if address and mode:
            db.update_trading_mode(address, mode)
            print(f">>> DATABASE: Updated default mode to {mode} for {address}")
        
        gemini_key = user_conf["gemini_api_key"] if (user_conf and "gemini_api_key" in user_conf.keys()) else None
        
        price_val = float(price_str)
        analysis_result = strategy_v2.analyze(
            symbol, price_val, klines, news_text, intel_data,
            mode=final_mode,
            risk_profile=risk_profile,
            custom_keys={"gemini_api_key": gemini_key}
        )

        return {
            "symbol": symbol,
            "current_price": price_str,
            "analysis": analysis_result,
            "sentiment": {"trend_direction": analysis_result.get("decision"), "impact_score": 5},
            "sentiment_score": 5,
            "risk_profile": risk_profile,
            "market_intel": intel_data,
            "news": news, # Include raw news list
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/chart/klines")
async def get_market_klines(symbol: str, interval: str = "15m", limit: int = 100):
    klines = await retry_async(client.get_klines, symbol, interval, limit)
    return {"klines": klines}

@app.get("/api/markets")
async def get_available_markets():
    markets = await retry_async(client.get_markets)
    return {"markets": markets}

@app.get("/api/settings")
def get_settings(address: Optional[str] = Query(None)):
    if address == "undefined": address = None
    config = db.get_config(address) if db else None
    return {
        "is_active": config["is_active"] if config else 0,
        "private_key": config["private_key"] if config else "",
        "symbol": config["symbol"] if config else Config.TARGET_SYMBOL,
        "account_id": config["account_id"] if config else Config.SODEX_ACCOUNT_ID,
        "gemini_api_key": config["gemini_api_key"] if config else "",
        "openrouter_api_key": config["openrouter_api_key"] if config else "",
        "trading_mode": config["trading_mode"] if config and "trading_mode" in config.keys() else "MOMENTUM",
        "last_auto_log": config["last_auto_log"] if config and "last_auto_log" in config.keys() else "Waiting for next scan..."
    }

@app.post("/api/settings/save")
async def save_settings(req: Request):
    data = await req.json()
    address = data.get("address")
    pk = data.get("private_key")
    aid = data.get("account_id")
    sym = data.get("symbol", Config.TARGET_SYMBOL)
    lev = data.get("leverage", Config.DEFAULT_LEVERAGE)
    gemini_key = data.get("gemini_api_key")
    openrouter_key = data.get("openrouter_api_key")
    trading_mode = data.get("trading_mode", "MOMENTUM")
    
    if not address or not pk:
        return {"code": -1, "error": "Address and Private Key are mandatory"}
    
    if db:
        db.save_config(address, pk, aid, sym, lev, gemini_key, openrouter_key, trading_mode)
    return {"status": "success"}


@app.post("/api/settings/toggle")
async def toggle_auto_trading(address: str = Query(...), active: bool = Query(...)):
    if db: 
        print(f">>> API: Toggling Bot for {address} to {active}")
        db.toggle_bot_active(address, active)
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
                            # print(f"DEBUG OPEN_ORDERS ({len(raw_orders)} found): {json.dumps(raw_orders[0], indent=2)}")
                            pass
                        
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
        # Step 1: Dynamic Market Metadata Resolution
        import requests 
        symbol_id = 1
        tick_size = 0.01 
        step_size = 0.1 
        
        try:
            # Official Sodex Endpoint for Symbol Metadata
            sym_url = f"{client.base_url}/markets/symbols?symbol={req.symbol}"
            resp = await asyncio.to_thread(requests.get, sym_url, timeout=5)
            if resp.status_code == 200:
                sym_data = resp.json().get("data", [])
                if sym_data:
                    meta = sym_data[0] # Get the first match
                    symbol_id = int(meta.get("symbolID") or meta.get("id") or symbol_id)
                    tick_size = float(meta.get("tickSize") or tick_size)
                    step_size = float(meta.get("stepSize") or step_size)
                    print(f"DEBUG: Official Metadata for {req.symbol} -> ID:{symbol_id}, Tick:{tick_size}, Step:{step_size}")
                else:
                    print(f"DEBUG: Symbol {req.symbol} not found in official symbols list. Using defaults.")
        except Exception as e:
            print(f"DEBUG: Failed to fetch official market metadata: {e}")





        print(f"--- FINAL MARKET METADATA FOR {req.symbol} ---")
        print(f"    - Resolved ID: {symbol_id}")
        print(f"    - Applied Tick Size: {tick_size}")
        print(f"    - Applied Step Size: {step_size}")


        # Rounding Helpers using Decimal for high precision
        from decimal import Decimal, ROUND_HALF_UP
        def round_step(value, step):
            if not value or not step or step == 0: return str(value)
            try:
                d_val = Decimal(str(value))
                d_step = Decimal(str(step))
                # Calculate number of decimals from step
                prec_str = str(d_step).rstrip('0')
                precision = abs(prec_str.find('.') - len(prec_str)) - 1 if '.' in prec_str else 0
                
                # Round to nearest multiple of step
                rounded = (d_val / d_step).to_integral_value(rounding=ROUND_HALF_UP) * d_step
                # Format with fixed precision
                return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
            except:
                return str(value)

        # Apply rounding to request parameters
        clean_price = round_step(req.price or 0, tick_size)
        clean_qty = round_step(req.quantity or 0, step_size)
        
        # Step 2: Prep Leverage Payload
        from collections import OrderedDict
        
        # FETCH Private Key from DB
        conf = db.get_config(req.address) if db else {}
        signing_key = conf.get("private_key")
        
        if not signing_key:
            return {"code": -1, "error": "Private Key not found. Check settings."}

        lev_params = OrderedDict([
            ("accountID",  int(req.account_id)),
            ("symbolID",   int(symbol_id)),
            ("leverage",   int(req.leverage)),
            ("marginMode", int(req.margin_mode))
        ])
        
        # ... (rest of the logic uses clean_price and clean_qty) ...
        # (I need to ensure the following code uses these cleaned variables)

        
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
        print(f">>> UNIFIED: Step 2 - Executing {req.symbol} Order (Clean Price: {clean_price}, Clean Qty: {clean_qty})")
        from collections import OrderedDict
        # Step 4: Sign & Hit Order
        nonce_ord = int(time.time() * 1000) + 1 # Ensure unique nonce
        cl_ord_id = f"{req.account_id}-{nonce_ord}"
        
        # Use the signing_key fetched from DB above

        # Build order item based on type
        is_market = int(req.order_type) == 2
        curr_p = float(req.price or 0)
        
        # SANITY CHECK: Validate TP/SL positions to avoid "stopPrice is invalid"
        final_tp = None
        final_sl = None
        
        if req.tp_price:
            tp_val = float(req.tp_price)
            if (int(req.side) == 1 and tp_val > curr_p) or (int(req.side) == 2 and tp_val < curr_p):
                final_tp = round_step(tp_val, tick_size)
            else:
                print(f"⚠️ WARNING: AI TP ({tp_val}) invalid for side {req.side} @ {curr_p}. Skipped.")

        if req.sl_price:
            sl_val = float(req.sl_price)
            if (int(req.side) == 1 and sl_val < curr_p) or (int(req.side) == 2 and sl_val > curr_p):
                final_sl = round_step(sl_val, tick_size)
            else:
                print(f"⚠️ WARNING: AI SL ({sl_val}) invalid for side {req.side} @ {curr_p}. Skipped.")

        has_bracket = bool(final_tp or final_sl)
        
        # Order of keys is CRITICAL for SoDEX signature
        order_item = OrderedDict()
        order_item["clOrdID"] = str(cl_ord_id)
        order_item["modifier"] = 3 if has_bracket else 1
        order_item["side"] = int(req.side)
        order_item["type"] = int(req.order_type)
        order_item["timeInForce"] = 3 if is_market else 1
        
        if not is_market:
            order_item["price"] = str(clean_price)
            
        order_item["quantity"] = str(clean_qty)
        order_item["reduceOnly"] = False
        order_item["positionSide"] = 1

        orders_list = [order_item]

        # Add TP/SL Orders if they passed sanity check
        if final_tp:
            orders_list.append(OrderedDict([
                ("clOrdID",      f"{cl_ord_id}-tp"),
                ("modifier",     4), # ATTACHED_STOP
                ("side",         2 if int(req.side) == 1 else 1),
                ("type",         2), # MARKET
                ("timeInForce",  3),
                ("quantity",     str(clean_qty)),
                ("stopPrice",    str(final_tp)),
                ("stopType",     2),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))
        
        if final_sl:
            orders_list.append(OrderedDict([
                ("clOrdID",      f"{cl_ord_id}-sl"),
                ("modifier",     4), # STOP_LOSS
                ("side",         2 if int(req.side) == 1 else 1),
                ("type",         2), # MARKET
                ("timeInForce",  3),
                ("quantity",     str(clean_qty)),
                ("stopPrice",    str(final_sl)),
                ("stopType",     1),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))

        print(f">>> SODEX: Executing {req.symbol} Order...")
        print(f"    - Side: {'LONG' if int(req.side) == 1 else 'SHORT'}")
        print(f"    - Type: {'MARKET' if is_market else 'LIMIT'}")
        print(f"    - Quantity: {req.quantity}")
        print(f"    - Leverage: x{req.leverage}")
        if req.tp_price: print(f"    - TP: {req.tp_price}")
        if req.sl_price: print(f"    - SL: {req.sl_price}")

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
        
        if order_res.get("code") == 0:
            print(f"✅ SODEX SUCCESS: Order placed successfully. Response: {order_res.get('msg')}")
        else:
            print(f"❌ SODEX FAILED: {order_res.get('error') or order_res.get('msg')}")
            
        return order_res

    except Exception as e:
        return {"code": -1, "error": str(e)}

class CloseRequest(BaseModel):
    address: str
    symbol: str
    side: str
    quantity: float

@app.post("/api/trade/close")
async def close_position(req: CloseRequest):
    """
    Manually close an active position.
    """
    try:
        user_conf = db.get_config(req.address)
        if not user_conf:
            raise HTTPException(status_code=404, detail="User not found")
            
        private_key = user_conf.get("private_key")
        account_id = user_conf.get("account_id")
        
        if not private_key or not account_id:
            raise HTTPException(status_code=400, detail="User credentials missing")
            
        # Create client for this user
        user_client = SodexClient(private_key=private_key)
        
        # Resolve Symbol ID
        sym_info = user_client.get_symbol_info(req.symbol)
        symbol_id = sym_info["id"]
        
        # Map side string to integer
        # 1 = LONG, 2 = SHORT
        side_int = 1 if req.side.upper() == "LONG" else 2
        
        print(f"DEBUG: Manual Close Request for {req.address} | {req.symbol} (ID: {symbol_id}) | Side: {req.side} ({side_int}) | Qty: {req.quantity}")
        
        # Use the newly added close_position method in SDK
        resp = await retry_async(
            user_client.close_position,
            account_id=int(account_id),
            symbol_id=symbol_id,
            side=side_int,
            quantity=float(req.quantity)
        )
        db.add_log(f"Manual Close: {req.symbol} Qty:{req.quantity}", "manual")
        return {"status": "success", "response": resp}
        
    except Exception as e:
        print(f"CLOSE ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
