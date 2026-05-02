import asyncio
import time
from config import Config
from sdk.client import SodexClient
from sdk.websocket import SodexWS
from agents.news_aggregator import NewsAggregator
from agents.strategy_engine import StrategyEngine
from sdk.auth import SodexAuth
from sdk.database import DatabaseManager

# Trading States
STATE_SCANNING = "SCANNING"
STATE_POSITION = "POSITION"

db = DatabaseManager()

async def main():
    print("Initializing SoDEX Perpetual Bot (HYBRID LOOP MODE)...")
    
    # Setup
    client = SodexClient(is_spot=False)
    ws = SodexWS(is_spot=False)
    news_agg = NewsAggregator()
    strategy = StrategyEngine()

    # Dynamic Config from DB
    bot_conf = db.get_config()
    if bot_conf:
        SYMBOL = bot_conf.get("symbol", Config.TARGET_SYMBOL)
        account_id = bot_conf.get("account_id", Config.SODEX_ACCOUNT_ID)
        private_key = bot_conf.get("private_key") or Config.SODEX_PRIVATE_KEY
        print("Loaded dynamic configuration from database.")
    else:
        SYMBOL = Config.TARGET_SYMBOL
        account_id = Config.SODEX_ACCOUNT_ID
        private_key = Config.SODEX_PRIVATE_KEY

    symbol_id = 1 # BTC-PERP
    master_addr = SodexAuth.recover_address(private_key)

    print(f"Using AccountID: {account_id} | Master Wallet: {master_addr}")

    # Start WebSocket in background
    asyncio.create_task(ws.start())

    # Initial State Sync: Check if we already have a position open
    print("Checking for existing positions to sync state...")
    init_state = client.get_perps_positions(master_addr, account_id)
    if init_state and init_state.get("code") == 0 and init_state.get("data"):
        # Schema says data is PerpsAccountOpenPosition which has a 'positions' array
        positions = init_state["data"].get("positions") or []
        if isinstance(positions, list) and any(isinstance(pos, dict) and pos.get("symbol") == SYMBOL and float(pos.get("size", 0)) != 0 for pos in positions):
            print(f"Existing {SYMBOL} position detected! Syncing to STATE_POSITION.")
            current_state = STATE_POSITION
        else:
            current_state = STATE_SCANNING
    else:
        current_state = STATE_SCANNING

    print(f"Bot started. Initial State: {current_state}")

    while True:
        try:
            if current_state == STATE_SCANNING:
                # ---------------------------------------------------------
                # STATE A: Idle & Scanning
                # ---------------------------------------------------------
                print(f"[{time.strftime('%H:%M:%S')}] Scanning market for opportunities...")
                db.add_log(f"Scanning market for {SYMBOL}...", "info")
                
                # Double Check: Ensure no position OR pending orders exist before scanning
                perps_orders = client.get_perps_orders(master_addr, account_id)
                has_pending = False
                if perps_orders and perps_orders.get("code") == 0 and perps_orders.get("data"):
                    pending_list = perps_orders["data"].get("orders") or []
                    # Check if any order is a 'Parent' order (modifier 1 or 3) and not a TP/SL (stopType 0)
                    if any(o.get("symbol") == SYMBOL and o.get("stopType") == 0 for o in pending_list):
                        has_pending = True

                quick_state = client.get_perps_state(master_addr)
                if quick_state and quick_state.get("code") == 0 and quick_state.get("data"):
                    positions = quick_state["data"].get("P") or []
                    has_pos = any(pos["s"] == SYMBOL and float(pos.get("sz", 0)) != 0 for pos in positions)
                    
                    if has_pos or has_pending:
                        print(f"Safety Trigger: {'Position' if has_pos else 'Pending Order'} exists. Switching to STATE_POSITION.")
                        current_state = STATE_POSITION
                        continue

                # Fetch Market Data
                p_str = client.get_mark_price(SYMBOL)
                if not p_str:
                    print("Failed to fetch price. Retrying...")
                    await asyncio.sleep(5)
                    continue
                
                p = float(p_str)
                klines = client.get_klines(SYMBOL, interval="15m", limit=20)
                news = news_agg.fetch_latest_news(SYMBOL)
                news_text = "\n".join([f"- {n['title']}" for n in news]) if news else "No news available."

                # AI Analysis
                result = strategy.ensemble_analyze(SYMBOL, p_str, "OPEN", news_text, klines)
                decision = result.get("decision", "HOLD")
                
                # Robust reasoning extraction
                reasoning = result.get("reasoning", "")
                if isinstance(reasoning, dict):
                    reasoning_str = reasoning.get("strategy", str(reasoning))
                else:
                    reasoning_str = str(reasoning)

                print(f"AI Decision: {decision}")
                db.add_log(f"AI Analysis: {decision} ({reasoning_str})", "ai")

                if decision in ["LONG", "SHORT"]:
                    # Confirmation & Execution
                    print(f"Triggering {decision} position...")
                    
                    # Final Safety Check immediately before execution
                    final_check = client.get_perps_state(master_addr)
                    if final_check and final_check.get("code") == 0 and final_check.get("data"):
                        positions = final_check["data"].get("P") or []
                        if any(pos["s"] == SYMBOL and float(pos.get("sz", 0)) != 0 for pos in positions):
                            print("ABORT: Position was opened by another process or previous task.")
                            current_state = STATE_POSITION
                            continue

                    # Calculate ATR for TP/SL
                    atr = 250.0
                    if klines:
                        tr_sum = sum([float(k.get("h", 0)) - float(k.get("l", 0)) for k in klines])
                        atr = tr_sum / len(klines)

                    # Calculate Quantity (20% Margin)
                    balance = client.get_perps_balance(master_addr)
                    margin_to_use = balance * 0.20
                    leverage = Config.DEFAULT_LEVERAGE
                    position_size_usd = margin_to_use * leverage
                    quantity_btc = position_size_usd / p
                    quantity_str = f"{quantity_btc:.4f}".rstrip("0").rstrip(".")

                    side = 1 if decision == "LONG" else 2
                    
                    # Momentum / Limit Price Logic
                    params = result.get("params", {})
                    limit_price = params.get("limit_price")
                    
                    if limit_price:
                        try:
                            exec_price = str(int(float(limit_price)))
                            print(f"Momentum Entry Detected: Queuing order at {exec_price}")
                            db.add_log(f"Momentum Entry: Queuing {decision} at {exec_price}", "info")
                        except:
                            exec_price = str(int(p))
                    else:
                        exec_price = str(int(p)) # Market-like limit

                    if side == 1: # LONG
                        sl_price = str(int(float(exec_price) - (2 * atr)))
                        tp_price = str(int(float(exec_price) + (4 * atr)))
                    else: # SHORT
                        sl_price = str(int(float(exec_price) + (2 * atr)))
                        tp_price = str(int(float(exec_price) - (4 * atr)))

                    print(f"Opening {decision} | Entry: {exec_price}, SL: {sl_price}, TP: {tp_price}")
                    
                    res = client.place_order_with_tpsl(
                        account_id=account_id,
                        symbol_id=symbol_id,
                        side=side,
                        order_type=1,
                        quantity=quantity_str,
                        price=exec_price,
                        tp_price=tp_price,
                        sl_price=sl_price
                    )

                    if res.get("code") == 0:
                        print("Position opened successfully. Moving to POSITION state.")
                        current_state = STATE_POSITION
                    else:
                        print(f"Failed to open position: {res.get('error')}")
                
                await asyncio.sleep(30) # Scan every 30 seconds

            elif current_state == STATE_POSITION:
                # ---------------------------------------------------------
                # STATE B: Position Management
                # ---------------------------------------------------------
                pos_data = client.get_perps_positions(master_addr, account_id)
                if not pos_data or pos_data.get("code") != 0:
                    print("Error fetching positions. Retrying...")
                    await asyncio.sleep(5)
                    continue

                # The schema says data contains a 'positions' array
                positions = []
                if pos_data.get("data") and isinstance(pos_data["data"], dict):
                    positions = pos_data["data"].get("positions") or []
                
                # We need open orders for TP/SL from the dedicated endpoint
                orders_data = client.get_perps_orders(master_addr, account_id)
                open_orders = []
                if orders_data and orders_data.get("code") == 0 and orders_data.get("data"):
                    # Schema says data is PerpsAccountOpenOrder which has an 'orders' array
                    open_orders = orders_data["data"].get("orders") or []
                
                # Check if position is still open
                my_pos = next((pos for pos in positions if isinstance(pos, dict) and pos.get("symbol") == SYMBOL), None)
                
                if not my_pos or float(my_pos.get("size", 0)) == 0:
                    # Check if there's a pending limit order still waiting to be filled
                    has_pending = any(o.get("symbol") == SYMBOL and o.get("stopType") == 0 for o in open_orders)
                    
                    if not has_pending:
                        print("No position and no pending orders. Returning to SCANNING.")
                        db.add_log(f"Trade cycle on {SYMBOL} finished.", "info")
                        db.update_position(SYMBOL, "NONE", 0, 0, 0, 0)
                        current_state = STATE_SCANNING
                        continue
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] Waiting for Limit Order to fill...")
                        sz = 0
                        pending_order = next((o for o in open_orders if o.get("symbol") == SYMBOL and o.get("stopType") == 0), {})
                        pending_side = "LONG" if pending_order.get("side") == 1 else "SHORT"
                        side_in_pos = f"PENDING_{pending_side}"
                        unrealized_pnl = 0
                        entry_price = float(pending_order.get("price") or 0)
                        tp_price = 0
                        sl_price = 0
                        p_str = client.get_mark_price(SYMBOL)
                        mark_price = float(p_str or 0)
                else:
                    # --- EXTRACT DATA BASED ON SODEX SCHEMA ---
                    sz = float(my_pos["size"])
                    side_in_pos = "LONG" if sz > 0 else "SHORT"
                    p_str = client.get_mark_price(SYMBOL)
                    mark_price = float(p_str or 0)
                    entry_price = float(my_pos.get("avgEntryPrice") or 0)

                    # Manual PnL Calculation
                    unrealized_pnl = (mark_price - entry_price) * sz
                    
                    # Extract TP/SL from open orders
                    tp_price = 0
                    sl_price = 0
                    for o in open_orders:
                        if isinstance(o, dict) and o.get("symbol") == SYMBOL:
                            st = o.get("stopType")
                            sp = o.get("stopPrice")
                            if str(st) == "2": tp_price = float(sp or 0)
                            if str(st) == "1": sl_price = float(sp or 0)

                # Schema keys: leverage, avgEntryPrice
                pos_leverage = int(my_pos.get("leverage") or Config.DEFAULT_LEVERAGE)

                print(f"[{time.strftime('%H:%M:%S')}] Managing {side_in_pos} position. PnL: {unrealized_pnl:.4f} | Entry: {entry_price}")
                
                # Update DB with current position info
                db.update_position(
                    SYMBOL, side_in_pos, sz, 
                    entry_price, 
                    mark_price, 
                    unrealized_pnl,
                    tp_price, sl_price,
                    pos_leverage
                )
                
                # Update stats with accurate data for dashboard cards
                balance = client.get_perps_balance(master_addr)
                db.update_stats(balance, unrealized_pnl, pos_leverage)

                news = news_agg.fetch_latest_news(SYMBOL)
                news_text = "\n".join([f"- {n['title']}" for n in news]) if news else "No news available."
                
                # Fetch klines for context (NEW: allowing AI to see trends while in position)
                klines = client.get_klines(SYMBOL, interval="15m", limit=20)
                
                # AI Check for Exit or Switch
                result = strategy.ensemble_analyze(SYMBOL, p_str, "CLOSE", news_text, klines)
                exit_decision = result.get("decision", "HOLD")
                
                # If AI says CLOSE or the opposite side
                # For PENDING orders, we also close if AI gives a DIFFERENT limit_price (Switching to better entry)
                should_close = False
                params = result.get("params", {})
                new_limit = params.get("limit_price")

                if exit_decision == "CLOSE":
                    should_close = True
                elif "PENDING" in side_in_pos:
                    intended_side = side_in_pos.replace("PENDING_", "")
                    if exit_decision != "HOLD":
                        if exit_decision != intended_side:
                            should_close = True
                        elif new_limit and str(int(float(new_limit))) != str(int(entry_price)):
                            print(f"Switching Pending Order: New better entry found at {new_limit}")
                            should_close = True
                elif exit_decision != "HOLD" and exit_decision != side_in_pos:
                    should_close = True

                if should_close:
                    print(f"AI OVERRIDE DETECTED: Decision={exit_decision}. Closing/Cancelling current setup.")

                    
                    # 1. Cancel all open orders (TP/SL) for this symbol first
                    symbol_orders = [o["i"] for o in open_orders if o["s"] == SYMBOL]
                    if symbol_orders:
                        print(f"Cancelling TP/SL orders: {symbol_orders}")
                        client.cancel_orders(account_id, symbol_id, symbol_orders)

                    # 2. Market Close (Only if we have an actual position)
                    if sz != 0:
                        close_side = 2 if sz > 0 else 1
                        quantity_str = str(abs(sz))
                        
                        print(f"Executing Market Close for {quantity_str} BTC...")
                        res = client.place_order(
                            account_id=account_id,
                            symbol_id=symbol_id,
                            side=close_side,
                            order_type=2, # MARKET
                            quantity=quantity_str,
                            price="0",
                            reduce_only=True
                        )
                    else:
                        # If it was just a pending order, we already cancelled it
                        res = {"code": 0}

                    if res.get("code") == 0:
                        print("Cleanup successful. Returning to SCANNING.")
                        current_state = STATE_SCANNING
                        continue # Immediate scan next loop
                    else:
                        print(f"Failed to close position: {res.get('error')}")

                await asyncio.sleep(20) # Monitor every 20 seconds

        except Exception as e:
            print(f"CRITICAL ERROR in main loop: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    import os
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Force exiting SoDEX Bot...")
        os._exit(0)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        os._exit(1)
