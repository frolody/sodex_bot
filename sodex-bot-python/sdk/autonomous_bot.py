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

class AutonomousBot:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.client = SodexClient(is_spot=False)
        self.news_agg = NewsAggregator()
        self.strategy = StrategyEngine()
        self.is_running = False
        self.stop_event = asyncio.Event()

    async def start_loop(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        
        print("Starting Autonomous Trading Loop (with 5s safety delay)...")
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=5)
            return # If event is set during delay
        except asyncio.TimeoutError:
            pass # Timeout is expected during normal delay
        
        while self.is_running:
            try:
                # 1. Check if Bot is Active in DB
                conf = self.db.get_config()
                if not conf or not conf.get("is_active"):
                    # print("Autonomous Bot is PAUSED.")
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        pass
                    continue

                # 2. Extract Config
                SYMBOL = conf.get("symbol", Config.TARGET_SYMBOL)
                account_id = conf.get("account_id", Config.SODEX_ACCOUNT_ID)
                # Use EVM_WALLET_PRIVATE_KEY for your 0xefaf... wallet
                private_key = conf.get("private_key") or getattr(Config, 'EVM_WALLET_PRIVATE_KEY', Config.SODEX_PRIVATE_KEY)
                master_addr = SodexAuth.recover_address(private_key)
                symbol_id = 1 # BTC-PERP

                # 3. Simple State Management
                state_resp = self.client.get_perps_state(master_addr)
                has_pos = False
                if state_resp and state_resp.get("code") == 0 and state_resp.get("data"):
                    positions = state_resp["data"].get("P") or []
                    has_pos = any(pos["s"] == SYMBOL and float(pos.get("sz", 0)) != 0 for pos in positions)

                if not has_pos:
                    # SCANNING STATE
                    p_str = self.client.get_mark_price(SYMBOL)
                    if p_str:
                        klines = self.client.get_klines(SYMBOL, interval="15m", limit=20)
                        news = self.news_agg.fetch_latest_news(SYMBOL)
                        news_text = "\n".join([f"- {n['title']}" for n in news]) if news else ""
                        
                        result = self.strategy.ensemble_analyze(SYMBOL, p_str, "OPEN", news_text, klines)
                        decision = result.get("decision", "HOLD")
                        
                        if decision in ["LONG", "SHORT"]:
                            # Execute Trade (Custodial)
                            print(f"AUTO-BOT: Triggering {decision} for {SYMBOL}")
                            
                            params = result.get("params", {})
                            side = 1 if decision == "LONG" else 2
                            p_float = float(p_str)
                            
                            # SAFETY: Calculate Default TP/SL if AI misses them
                            tp_price = params.get("tp_price")
                            sl_price = params.get("sl_price")
                            
                            if not tp_price or not sl_price:
                                print("AUTO-BOT: AI missing TP/SL. Calculating defaults...")
                                if decision == "LONG":
                                    tp_price = str(round(p_float * 1.015, 1)) # +1.5%
                                    sl_price = str(round(p_float * 0.99, 1))   # -1.0%
                                else:
                                    tp_price = str(round(p_float * 0.985, 1)) # -1.5%
                                    sl_price = str(round(p_float * 1.01, 1))  # +1.0%
                            
                            bal = self.client.get_perps_balance(master_addr)
                            qty = (bal * 0.1 * Config.DEFAULT_LEVERAGE) / p_float # Safe 10% margin
                            qty_str = f"{qty:.4f}".rstrip("0").rstrip(".")
                            
                            self.db.add_log(f"Auto-Trade: Opening {decision} (Market) at {p_str} with TP:{tp_price} SL:{sl_price}", "auto")
                            
                            # FORCE Market Entry (2) with TP/SL as requested
                            self.client.place_order_with_tpsl(
                                account_id, symbol_id, side, 2, qty_str, p_str, tp_price, sl_price
                            )
                
                # Loop every 30s, but wake up instantly if stop_event is set
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
            except Exception as e:
                print(f"Autonomous Bot Error: {e}")
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

    def stop(self):
        self.is_running = False
        self.stop_event.set()
