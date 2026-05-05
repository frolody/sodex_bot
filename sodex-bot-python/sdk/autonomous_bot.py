import asyncio
import time
from config import Config
from sdk.client import SodexClient
from sdk.websocket import SodexWS
from agents.news_aggregator import NewsAggregator
from sdk.auth import SodexAuth
from sdk.database import DatabaseManager
from agents.strategy_v2 import StrategyV2
from agents.market_intelligence import MarketIntelligence

# Trading States
STATE_SCANNING = "SCANNING"
STATE_POSITION = "POSITION"

class AutonomousBot:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.client = SodexClient(is_spot=False)
        self.news_agg = NewsAggregator()
        self.strategy = StrategyV2()
        self.market_intel = MarketIntelligence()
        self.is_running = False
        self.stop_event = asyncio.Event()
        self.active_tasks = {} # Track running tasks per user

    async def start_loop(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        
        print("Starting Parallel Multi-User Autonomous Trading Loop...")
        
        while self.is_running:
            try:
                # 1. Fetch ALL Active Users from DB
                import sqlite3
                conn = sqlite3.connect(self.db.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM bot_config WHERE is_active = 1")
                active_users = [dict(row) for row in cursor.fetchall()]
                conn.close()

                if not active_users:
                    interval = Config.TRADING_INTERVAL_SECONDS
                    print(f">>> AUTONOMOUS ENGINE: No active users. Checking again in {interval}s...")
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=interval)
                    except asyncio.TimeoutError:
                        pass
                    continue

                # 2. Spawn a Parallel Task for each User if not already running
                for user_conf in active_users:
                    addr = user_conf.get("wallet_address")
                    if addr in self.active_tasks and not self.active_tasks[addr].done():
                        print(f"--- Task for {addr[:6]} still running. Skipping this cycle. ---")
                        continue
                    
                    self.active_tasks[addr] = asyncio.create_task(self.process_user_trade(user_conf))
                
                # Global cycle sleep using config
                interval = Config.TRADING_INTERVAL_SECONDS
                print(f">>> AUTONOMOUS ENGINE: Cycle complete. Sleeping for {interval}s...")
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                print(f"Global Loop Error: {e}")
                await asyncio.sleep(10)

    async def process_user_trade(self, conf):
        """
        Isolated trading logic for a single user.
        Runs in parallel with other users.
        """
        try:
            SYMBOL = conf.get("symbol", Config.TARGET_SYMBOL)
            account_id = conf.get("account_id", Config.SODEX_ACCOUNT_ID)
            private_key = conf.get("private_key")
            if not private_key: return
            
            master_addr = SodexAuth.recover_address(private_key)
            print(f">>> AUTONOMOUS: Starting analysis for {master_addr[:6]} ({SYMBOL})")
            
            # CRITICAL: Create a NEW isolated client for this user to avoid parallel conflicts
            user_client = SodexClient(
                is_spot=False, 
                private_key=private_key,
                api_key_name=master_addr # On testnet, API name is usually the address
            )
            
            # Use User-Specific API Keys if available for AI
            user_gemini = conf.get("gemini_api_key")
            user_openrouter = conf.get("openrouter_api_key")
            custom_keys = {
                "gemini_api_key": user_gemini,
                "openrouter_api_key": user_openrouter
            }
            
            # 3. Check Position State
            state_resp = user_client.get_perps_state(master_addr)
            active_pos = None
            if state_resp and state_resp.get("code") == 0 and state_resp.get("data"):
                positions = state_resp["data"].get("P") or []
                for pos in positions:
                    if pos["s"] == SYMBOL and float(pos.get("sz", 0)) != 0:
                        active_pos = pos
                        break

            # 4. FETCH MARKET METADATA (Needed for rounding)
            import requests
            symbol_id = 1
            tick_size = 0.1
            step_size = 0.0001 # Corrected default for BTC-USD
            try:
                sym_url = f"{user_client.base_url}/markets/symbols"
                resp = requests.get(sym_url, timeout=5)
                if resp.status_code == 200:
                    meta_data = resp.json().get("data", [])
                    for meta in meta_data:
                        if meta.get("name") == SYMBOL:
                            symbol_id = int(meta.get("id") or 1)
                            tick_size = float(meta.get("tickSize") or 0.1)
                            step_size = float(meta.get("stepSize") or 0.0001)
                            break
            except: pass

            # 5. SCANNING & ANALYSIS (Always run even if pos exists)
            p_str = user_client.get_mark_price(SYMBOL)
            if not p_str: return
            p_float = float(p_str)

            klines = user_client.get_klines(SYMBOL, interval="15m", limit=50)
            news_sym = SYMBOL.split("-")[0]
            news = self.news_agg.fetch_latest_news(news_sym, limit=20)
            news_text = "\n".join([f"- {n['title']}" for n in news]) if news else ""
            intel_data = self.market_intel.get_comprehensive_intel(news_sym)

            # Fetch Balance
            balance_val = "100"
            try:
                bal_data = user_client.get_perps_balance(master_addr)
                balance_val = str(bal_data)
            except: pass

            risk_profile = conf.get("risk_profile", "SAFETY").upper()
            mode = conf.get('trading_mode', 'MOMENTUM')
            
            # AI Analysis
            result = self.strategy.analyze(
                SYMBOL, p_str, klines, news_text, intel_data,
                mode=mode, risk_profile=risk_profile, custom_keys=custom_keys
            )
            decision = result.get("decision", "HOLD")
            ai_score = result.get("confidence", 0)
            tech_log = result.get("technical_analysis", "Analyzing market...")
            
            from decimal import Decimal, ROUND_HALF_UP
            def round_step(value, step):
                if not value or not step or step == 0: return str(value)
                d_val = Decimal(str(value))
                d_step = Decimal(str(step))
                prec_str = str(d_step).rstrip('0')
                precision = abs(prec_str.find('.') - len(prec_str)) - 1 if '.' in prec_str else 0
                rounded = (d_val / d_step).to_integral_value(rounding=ROUND_HALF_UP) * d_step
                return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')

            # 6. ACTIVE POSITION MANAGEMENT LOGIC
            if active_pos:
                cur_side = int(active_pos.get("sd") or 1) # 1=LONG, 2=SHORT
                cur_size = float(active_pos.get("sz") or 0)
                entry_p = float(active_pos.get("ep") or p_float)
                
                print(f">>> OVERSIGHT [{master_addr[:6]}]: Active {SYMBOL} {'LONG' if cur_side==1 else 'SHORT'}. AI Score: {ai_score}")

                # FEATURE 1: TREND REVERSAL (Close & Reverse)
                is_reversal = (cur_side == 1 and decision == "SHORT") or (cur_side == 2 and decision == "LONG")
                if is_reversal and ai_score >= 0.75:
                    print(f"⚠️ REVERSAL DETECTED! Closing {SYMBOL} and switching sides.")
                    user_client.close_position(account_id, symbol_id, cur_side, cur_size)
                    self.db.add_log(f"Reversal! Closed {SYMBOL} to switch to {decision}", "auto")
                    active_pos = None # Allow to open new position below
                
                # FEATURE 2: SENTIMENT DEGRADATION (Defense)
                elif ai_score < 0.4:
                    print(f"🛡️ SENTIMENT DROPPED ({ai_score}). Tightening Stop Loss to Break-Even.")
                    # Tighten SL to entry + 0.1% buffer
                    new_sl = entry_p * 1.001 if cur_side == 1 else entry_p * 0.999
                    clean_sl = round_step(new_sl, tick_size)
                    
                    # EXECUTE: Update TP/SL on exchange
                    user_client.update_position_tpsl(
                        account_id, symbol_id, cur_side, cur_size,
                        tp_price=None, # Keep old TP or None
                        sl_price=clean_sl
                    )
                    
                    self.db.save_auto_log(master_addr, f"{SYMBOL}: Sentiment weak. Tightening SL to {clean_sl}")
                    return

                # FEATURE 3: PYRAMIDING (Scale-In)
                elif ai_score >= 0.95:
                    print(f"🔥 SUPER SIGNAL ({ai_score}). Scaling in to existing position.")
                    print(f"DEBUG [{master_addr[:6]}]: Current Size: {cur_size} | Available Bal: {balance_val}")
                    
                    # Safety: Don't scale in if available balance is too low (e.g. < $5)
                    if float(balance_val) < 5:
                        print(f"⚠️ SCALE-IN ABORTED: Insufficient available margin (${balance_val}).")
                        return

                    # Add 30% more size for momentum scaling
                    scale_qty = cur_size * 0.3
                    clean_scale_qty = round_step(scale_qty, step_size)
                    
                    if float(clean_scale_qty) > 0:
                        user_client.place_order(
                            account_id, symbol_id, cur_side, 
                            order_type=2, quantity=clean_scale_qty, 
                            price="0", reduce_only=False
                        )
                        self.db.save_auto_log(master_addr, f"{SYMBOL}: Momentum strong. Scaled in {clean_scale_qty}")
                    return

                else:
                    self.db.save_auto_log(master_addr, f"{SYMBOL}: Maintaining position. AI Confidence: {ai_score}")
                    return

            # 7. NEW POSITION EXECUTION (Only if active_pos is None)
            if decision not in ["LONG", "SHORT"]:
                return

            params = result.get("params", {})
            risk_leverage = int(params.get("leverage") or Config.DEFAULT_LEVERAGE)
            risk_margin_pct = float(params.get("margin_percent") or 10) / 100.0
            
            side = 1 if decision == "LONG" else 2
            tp_price = str(params.get("tp_price") or "")
            sl_price = str(params.get("sl_price") or "")
            
            if not tp_price or not sl_price:
                tp_price = str(p_float * 1.015) if decision == "LONG" else str(p_float * 0.985)
                sl_price = str(p_float * 0.99) if decision == "LONG" else str(p_float * 1.01)

            clean_price = round_step(p_float, tick_size)
            clean_tp = round_step(tp_price, tick_size)
            clean_sl = round_step(sl_price, tick_size)

            bal = float(balance_val)
            qty = (bal * risk_margin_pct * risk_leverage) / p_float
            clean_qty = round_step(qty, step_size)
            
            if float(clean_qty) <= 0:
                print(f"ABORT [{master_addr[:6]}]: Calculated quantity ({qty}) is too small for step_size ({step_size}).")
                return

            self.db.add_log(f"Auto-Trade [{master_addr[:6]}]: Opening {decision} {SYMBOL} Qty:{clean_qty} at {clean_price}", "auto")
            
            # STEP A: Sync Leverage First (ONLY if no position is open)
            if not active_pos:
                try:
                    print(f">>> AUTONOMOUS: Syncing leverage to x{risk_leverage} for {SYMBOL}")
                    user_client.update_leverage(account_id, symbol_id, risk_leverage)
                    time.sleep(0.5) 
                except Exception as le:
                    print(f"Leverage Sync Warning: {le}")

            # STEP B: Place Order with TP/SL
            user_client.place_order_with_tpsl(
                account_id, symbol_id, side, 2, clean_qty, clean_price, 
                clean_tp, clean_sl, leverage=risk_leverage
            )

        except Exception as e:
            print(f"Error processing user {conf.get('wallet_address')}: {e}")

    def stop(self):
        self.is_running = False
        self.stop_event.set()
