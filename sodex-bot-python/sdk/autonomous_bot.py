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
                    # print("No active users to process.")
                    await asyncio.sleep(10)
                    continue

                # 2. Spawn a Parallel Task for each User
                for user_conf in active_users:
                    asyncio.create_task(self.process_user_trade(user_conf))
                
                # Global cycle sleep (e.g., scan all users every 2 minutes)
                # This ensures we don't spam API keys too hard
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=120)
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
            
            # Use User-Specific API Keys if available
            user_gemini = conf.get("gemini_api_key")
            user_openrouter = conf.get("openrouter_api_key")
            custom_keys = {
                "gemini_api_key": user_gemini,
                "openrouter_api_key": user_openrouter
            }
            
            # 3. Check Position State
            state_resp = self.client.get_perps_state(master_addr)
            has_pos = False
            if state_resp and state_resp.get("code") == 0 and state_resp.get("data"):
                positions = state_resp["data"].get("P") or []
                has_pos = any(pos["s"] == SYMBOL and float(pos.get("sz", 0)) != 0 for pos in positions)

            if has_pos:
                # print(f"USER {master_addr[:6]}: Already has {SYMBOL} position. Skipping.")
                return

            # 4. SCANNING & ANALYSIS
            p_str = self.client.get_mark_price(SYMBOL)
            if not p_str: return

            klines = self.client.get_klines(SYMBOL, interval="15m", limit=20)
            news = self.news_agg.fetch_latest_news(SYMBOL)
            news_text = "\n".join([f"- {n['title']}" for n in news]) if news else ""
            intel_data = self.market_intel.get_comprehensive_intel(SYMBOL.split("-")[0])

            # Fetch Balance for Risk Scaling
            balance_val = "100"
            try:
                bal_data = self.client.get_perps_balance(master_addr)
                balance_val = str(bal_data)
            except: pass

            risk_profile = conf.get("risk_profile", "SAFETY").upper()
            mode = conf.get('trading_mode', 'MOMENTUM')
            print(f"PARALLEL-BOT: User {master_addr[:6]} analyzing with {mode} mode...")
            
            # AI Analysis (Pass custom keys)
            result = self.strategy.analyze(
                SYMBOL, p_str, klines, news_text, intel_data,
                mode=mode,
                risk_profile=risk_profile,
                custom_keys=custom_keys
            )
            decision = result.get("decision", "HOLD")
            
            if decision not in ["LONG", "SHORT"]:
                return

            # 5. EXECUTION LOGIC (Official Metadata-Aware)
            import requests
            symbol_id = 1
            tick_size = 0.01
            step_size = 0.1
            try:
                sym_url = f"{self.client.base_url}/markets/symbols?symbol={SYMBOL}"
                resp = requests.get(sym_url, timeout=5)
                if resp.status_code == 200:
                    meta_data = resp.json().get("data", [])
                    if meta_data:
                        meta = meta_data[0]
                        symbol_id = int(meta.get("symbolID") or meta.get("id") or 1)
                        tick_size = float(meta.get("tickSize") or 0.01)
                        step_size = float(meta.get("stepSize") or 0.1)
            except: pass

            params = result.get("params", {})
            risk_leverage = int(params.get("leverage") or Config.DEFAULT_LEVERAGE)
            risk_margin_pct = float(params.get("margin_percent") or 10) / 100.0
            
            from decimal import Decimal, ROUND_HALF_UP
            def round_step(value, step):
                if not value or not step or step == 0: return str(value)
                d_val = Decimal(str(value))
                d_step = Decimal(str(step))
                prec_str = str(d_step).rstrip('0')
                precision = abs(prec_str.find('.') - len(prec_str)) - 1 if '.' in prec_str else 0
                rounded = (d_val / d_step).to_integral_value(rounding=ROUND_HALF_UP) * d_step
                return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')

            print(f"PARALLEL-BOT: User {master_addr[:6]} triggering {decision} for {SYMBOL}")
            
            side = 1 if decision == "LONG" else 2
            p_float = float(p_str)
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
            
            self.db.add_log(f"Auto-Trade [{master_addr[:6]}]: {decision} {SYMBOL} at {clean_price} (Qty:{clean_qty})", "auto")
            
            self.client.place_order_with_tpsl(
                account_id, symbol_id, side, 2, clean_qty, clean_price, 
                clean_tp, clean_sl, 
                leverage=risk_leverage
            )

        except Exception as e:
            print(f"Error processing user {conf.get('wallet_address')}: {e}")

    def stop(self):
        self.is_running = False
        self.stop_event.set()
