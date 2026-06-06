import time
import json
import requests
from collections import OrderedDict
from config import Config
from sdk.auth import SodexAuth

class SodexClient:
    def __init__(self, is_spot=True, api_key_name=None, private_key=None, network_mode=None):
        self.is_spot = is_spot
        self.private_key = private_key or Config.SODEX_PRIVATE_KEY
        self.chain_id = Config.SODEX_CHAIN_ID
        self.api_key_name = api_key_name or Config.SODEX_API_NAME
        
        if not self.api_key_name and self.private_key:
            self.api_key_name = SodexAuth.recover_address(self.private_key)
        
        self.api_public_key = Config.SODEX_API_KEY
        
        # Use provided network_mode, fallback to Config
        is_testnet = Config.SODEX_TESTNET
        if network_mode:
            is_testnet = (network_mode == "testnet")
            
        domain = "testnet-gw" if is_testnet else "mainnet-gw"
        self.base_url = f"https://{domain}.sodex.dev/api/v1/perps"

    def _post_trade(self, method: str, params: dict, path: str = "trade/orders", nonce: int = None, http_method: str = "POST"):
        if not nonce:
            nonce = int(time.time() * 1000)
        
        signature = SodexAuth.create_signature(
            private_key=self.private_key,
            method=method,
            params=params,
            api_name=self.api_key_name,
            api_nonce=nonce,
            chain_id=self.chain_id,
            api_public_key=self.api_public_key
        )

        headers = {
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "X-API-Sign":    signature,
            "X-API-Nonce":   str(nonce),
        }
        
        if self.api_key_name and not Config.SODEX_TESTNET:
            headers["X-API-Key"] = str(self.api_key_name)

        url = f"{self.base_url}/{path}"
        json_body = json.dumps(params, separators=(',', ':'))
        
        try:
            print(f"DEBUG _POST_TRADE [{method}] URL: {url}")
            print(f"DEBUG _POST_TRADE PAYLOAD: {json.dumps(params)}")
            print(f"DEBUG _POST_TRADE HEADERS: X-API-Key={self.api_key_name} | Nonce={nonce}")
            if http_method.upper() == "DELETE":
                resp = requests.delete(url, data=json_body, headers=headers, timeout=10)
            else:
                resp = requests.post(url, data=json_body, headers=headers, timeout=10)
                
            print(f"DEBUG _POST_TRADE RESP: {resp.status_code} - {resp.text}")
            return resp.json()
        except Exception as e:
            return {"code": -1, "error": f"Network Error: {str(e)}"}

    def place_order(
        self,
        account_id:    int,
        symbol_id:     int  = 1,
        side:          int  = 1,
        order_type:    int  = 1,
        quantity:      str  = "0.001",
        price:         str  = "75000",
        position_side: int  = 1,
        reduce_only:   bool = False,
        modifier:      int  = 1,
    ) -> dict:
        t = int(time.time() * 1000)
        is_market = int(order_type) == 2
        
        order_item = OrderedDict([
            ("clOrdID",      str(t)),
            ("modifier",     int(modifier)),
            ("side",         int(side)),
            ("type",         int(order_type)),
            ("timeInForce",  int(3 if is_market else 1)),
            ("quantity",     str(quantity)),
            ("reduceOnly",   bool(reduce_only)),
            ("positionSide", int(position_side))
        ])

        if not is_market:
            new_order = OrderedDict()
            for k, v in order_item.items():
                if k == "quantity":
                    new_order["price"] = str(price)
                new_order[k] = v
            order_item = new_order

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders",    [order_item])
        ])

        return self._post_trade("newOrder", params, nonce=t)

    def modify_orders(self, account_id: int, symbol_id: int, modifies_list: list):
        if not modifies_list: return {"code": -1, "msg": "No modifications"}
        t = int(time.time() * 1000)
        
        items = []
        for m in modifies_list:
            item = OrderedDict()
            item["symbolID"] = int(symbol_id)
            # Add identity (either orderID or clOrdID)
            if "orderID" in m: item["orderID"] = int(m["orderID"])
            elif "clOrdID" in m: item["clOrdID"] = str(m["clOrdID"])
            
            # Add updated fields
            if "price" in m: item["price"] = str(m["price"])
            if "quantity" in m: item["quantity"] = str(m["quantity"])
            if "stopPrice" in m: item["stopPrice"] = str(m["stopPrice"])
            items.append(item)

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("modifies",  items)
        ])
        return self._post_trade("modifyOrder", params, path="trade/orders/modify", nonce=t, http_method="POST")

    def cancel_orders(self, account_id: int, symbol_id: int, order_ids: list):
        if not order_ids: return {"code": -1, "msg": "No order IDs"}
        t = int(time.time() * 1000)
        
        cancel_list = []
        for oid in order_ids:
            cancel_list.append(OrderedDict([
                ("symbolID", int(symbol_id)),
                ("orderID",  int(oid))
            ]))

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("cancels",   cancel_list)
        ])
        return self._post_trade("cancelOrder", params, nonce=t, http_method="DELETE")

    def cancel_all_orders_for_symbol(self, account_id: int, symbol_name: str):
        """
        Fetches all open orders and cancels those matching the symbol_name.
        """
        try:
            print(f">>>> SODEX: Cleaning up all orders for {symbol_name}...")
            raw_orders = self.get_perps_orders(SodexAuth.recover_address(self.private_key), account_id)
            data = raw_orders.get("data", {}) if isinstance(raw_orders, dict) else {}
            existing_orders = data.get("orders", []) if isinstance(data, dict) else []
            
            to_cancel = []
            actual_symbol_id = None
            
            for o in existing_orders:
                if not isinstance(o, dict): continue
                s = o.get("s") or o.get("symbol")
                if s == symbol_name:
                    oid = o.get("i") or o.get("orderID")
                    if oid: to_cancel.append(oid)
                    if not actual_symbol_id:
                        actual_symbol_id = o.get("si") or o.get("symbolID")

            if to_cancel:
                if not actual_symbol_id:
                    actual_symbol_id = self.get_symbol_info(symbol_name)["id"]
                
                print(f">>>> SODEX: Canceling {len(to_cancel)} orders for {symbol_name}")
                return self.cancel_orders(account_id, actual_symbol_id, to_cancel)
            
            return {"code": 0, "msg": "No orders to cancel"}
        except Exception as e:
            print(f"DEBUG: Error in cancel_all_orders_for_symbol: {e}")
            return {"code": -1, "error": str(e)}

    def update_leverage(self, account_id: int, symbol_id: int, leverage: int, margin_mode: int = 2):
        t = int(time.time() * 1000)
        params = OrderedDict([
            ("accountID",  int(account_id)),
            ("symbolID",   int(symbol_id)),
            ("leverage",   int(leverage)),
            ("marginMode", int(margin_mode))
        ])
        return self._post_trade("updateLeverage", params, path="trade/leverage", nonce=t)

    def update_position_tpsl(self, account_id: int, symbol_name: str, side: int = None, quantity: str = None, tp_price: str = None, sl_price: str = None):
        """
        Dynamically updates TP/SL for a position.
        First attempts to modify existing orders. If multiple exist or modification fails, 
        cleans up all orders for the symbol and places new ones.
        """
        symbol_info = self.get_symbol_info(symbol_name)
        actual_symbol_id = symbol_info["id"]
        
        raw_orders = self.get_perps_orders(SodexAuth.recover_address(self.private_key), account_id)
        data = raw_orders.get("data", {}) if isinstance(raw_orders, dict) else {}
        existing_orders = data.get("orders", []) if isinstance(data, dict) else []
        
        print(f"DEBUG: Updating TP/SL for {symbol_name}. Found {len(existing_orders)} total open orders.")
        
        tp_orders = []
        sl_orders = []
        to_cancel = []
        
        for o in existing_orders:
            if not isinstance(o, dict): continue
            s = o.get("s") or o.get("symbol")
            if s != symbol_name: continue
            
            oid = o.get("i") or o.get("orderID")
            if not oid: continue
            
            st = o.get("st") or o.get("stopType")
            if st in [2, "TAKE_PROFIT"]: 
                tp_orders.append(o)
            elif st in [1, "STOP_LOSS"]: 
                sl_orders.append(o)
            
            to_cancel.append(oid)

        # If we have exactly one TP and one SL (or only one of them and only that one is requested), 
        # we can try to modify. If we have multiples, it's safer to cancel all and redo.
        can_modify = (len(tp_orders) <= 1 and len(sl_orders) <= 1)
        
        if can_modify and (tp_orders or sl_orders):
            modifies = []
            if tp_orders and tp_price:
                oid = tp_orders[0].get("i") or tp_orders[0].get("orderID")
                modifies.append({"orderID": int(oid), "stopPrice": str(tp_price)})
            if sl_orders and sl_price:
                oid = sl_orders[0].get("i") or sl_orders[0].get("orderID")
                modifies.append({"orderID": int(oid), "stopPrice": str(sl_price)})
            
            if modifies:
                print(f">>>> SODEX: Modifying {len(modifies)} existing TP/SL orders for {symbol_name}...")
                res = self.modify_orders(account_id, actual_symbol_id, modifies)
                if res.get("code") == 0: return res
                print(f"MODIFY FAILED: {res.get('error') or res.get('msg')}. Proceeding to cleanup.")

        # 4. Cleanup and Place New Orders
        if to_cancel:
            print(f">>>> SODEX: Cleaning up {len(to_cancel)} old orders for {symbol_name}...")
            self.cancel_orders(account_id, actual_symbol_id, to_cancel)
            time.sleep(0.5)

        # If quantity/side not provided, fetch from position
        if not side or not quantity:
            pos_data = self.get_perps_positions(SodexAuth.recover_address(self.private_key), account_id)
            positions = pos_data.get("data", []) if isinstance(pos_data, dict) else []
            if isinstance(positions, dict): positions = positions.get("positions", [])
            
            target_pos = next((p for p in positions if (p.get("s") or p.get("symbol")) == symbol_name), None)
            if not target_pos:
                return {"code": -1, "msg": f"No open position found for {symbol_name}"}
                
            quantity = abs(float(target_pos.get("sz") or target_pos.get("size") or 0))
            side = 1 if float(target_pos.get("sz") or 0) > 0 else 2
        
        opp_side = 2 if int(side) == 1 else 1
        final_res = {"code": 0, "msg": "No updates needed"}
        
        # Place TP if provided OR if it was canceled and we want to keep it
        target_tp = tp_price or (tp_orders[0].get("sp") or tp_orders[0].get("stopPrice") if tp_orders else None)
        if target_tp:
            t_tp = int(time.time() * 1000000) # Use micro-nonce for extreme uniqueness
            print(f">>>> SODEX: Placing TP @ {target_tp} (ID: {t_tp})")
            tp_payload = OrderedDict([
                ("accountID", int(account_id)),
                ("symbolID",  int(actual_symbol_id)),
                ("orders", [OrderedDict([
                    ("clOrdID", f"{t_tp}-tp"),
                    ("modifier", 1),
                    ("side", opp_side),
                    ("type", 2),
                    ("timeInForce", 3),
                    ("quantity", str(quantity)), 
                    ("stopPrice", str(target_tp)),
                    ("stopType", 2),
                    ("triggerType", 2),
                    ("reduceOnly", True),
                    ("positionSide", 1)
                ])])
            ])
            final_res = self._post_trade("newOrder", tp_payload, nonce=int(t_tp/1000))
            time.sleep(0.3)
            
        # Place SL if provided OR if it was canceled and we want to keep it
        target_sl = sl_price or (sl_orders[0].get("sp") or sl_orders[0].get("stopPrice") if sl_orders else None)
        if target_sl:
            t_sl = int(time.time() * 1000000) + 1000
            print(f">>>> SODEX: Placing SL @ {target_sl} (ID: {t_sl})")
            sl_payload = OrderedDict([
                ("accountID", int(account_id)),
                ("symbolID",  int(actual_symbol_id)),
                ("orders", [OrderedDict([
                    ("clOrdID", f"{t_sl}-sl"),
                    ("modifier", 1),
                    ("side", opp_side),
                    ("type", 2),
                    ("timeInForce", 3),
                    ("quantity", str(quantity)),
                    ("stopPrice", str(target_sl)),
                    ("stopType", 1),
                    ("triggerType", 2),
                    ("reduceOnly", True),
                    ("positionSide", 1)
                ])])
            ])
            final_res = self._post_trade("newOrder", sl_payload, nonce=int(t_sl/1000))

        return final_res

    def place_order_with_tpsl(
        self,
        account_id: int,
        symbol_id: int,
        side: int,
        order_type: int,
        quantity: str,
        price: str,
        tp_price: str = None,
        sl_price: str = None,
        leverage: int = None
    ) -> dict:
        """
        Atomic entry: Places a Parent order (modifier 3) with attached TP/SL (modifier 4).
        Cleans up existing orders for the symbol first to prevent stacking.
        """
        # Cleanup first
        sym_info = self.get_symbol_info_by_id(symbol_id)
        if sym_info:
            self.cancel_all_orders_for_symbol(account_id, sym_info["name"])
            time.sleep(0.5)
        t = int(time.time() * 1000000) # Micro-nonce
        is_market = int(order_type) == 2
        
        orders = []
        # 1. Main Entry Order (Parent - Modifier 3)
        main_order = OrderedDict([
            ("clOrdID",      f"{t}-main"),
            ("modifier",     3), # Bracket Parent
            ("side",         int(side)),
            ("type",         int(order_type)),
            ("timeInForce",  int(3 if is_market else 1)),
            ("quantity",     str(quantity)),
            ("reduceOnly",   False),
            ("positionSide", 1)
        ])
        if not is_market: main_order["price"] = str(price)
        orders.append(main_order)

        opp_side = 2 if int(side) == 1 else 1
        
        # 2. Take Profit (Modifier 4)
        if tp_price:
            orders.append(OrderedDict([
                ("clOrdID",      f"{t}-tp"),
                ("modifier",     4),
                ("side",         opp_side),
                ("type",         2),
                ("timeInForce",  3),
                ("quantity",     str(quantity)),
                ("stopPrice",    str(tp_price)),
                ("stopType",     2),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))
        
        # 3. Stop Loss (Modifier 4)
        if sl_price:
            orders.append(OrderedDict([
                ("clOrdID",      f"{t}-sl"),
                ("modifier",     4),
                ("side",         opp_side),
                ("type",         2),
                ("timeInForce",  3),
                ("quantity",     str(quantity)),
                ("stopPrice",    str(sl_price)),
                ("stopType",     1),
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ]))

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders",    orders)
        ])

        return self._post_trade("newOrder", params, nonce=int(t/1000))

    def close_position(self, account_id: int, symbol_id: int, side: int, quantity: float) -> dict:
        """
        Closes a position by placing an opposite market order with reduceOnly=True.
        Side: 1 (LONG) -> SELL (2), 2 (SHORT) -> BUY (1)
        Also cancels all open orders for the symbol.
        """
        t = int(time.time() * 1000)
        opp_side = 2 if int(side) == 1 else 1
        
        # 1. Cancel all orders first
        sym_info = self.get_symbol_info_by_id(symbol_id)
        if sym_info:
            self.cancel_all_orders_for_symbol(account_id, sym_info["name"])
            time.sleep(0.5)

        print(f">>>> SODEX: Manual Closing Position (SymbolID: {symbol_id}, Qty: {quantity})")
        
        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders", [
                OrderedDict([
                    ("clOrdID",      f"{t}-close"),
                    ("modifier",     1), # Normal
                    ("side",         opp_side),
                    ("type",         2), # MARKET
                    ("timeInForce",  3), # IOC
                    ("quantity",     str(quantity)),
                    ("reduceOnly",   True),
                    ("positionSide", 1)
                ])
            ])
        ])
        
        return self._post_trade("newOrder", params, nonce=t)

    def get_perps_balance(self, address: str) -> float:
        try:
            # Use /state endpoint for more accurate margin awareness
            url = f"{self.base_url}/accounts/{address}/state"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            
            if data and data.get("code") == 0:
                body = data.get("data", {})
                # 'av' is Equity/Account Value, 'cm' is Current Margin used
                equity = float(body.get("av", 0))
                margin_used = float(body.get("cm", 0))
                
                # Available Margin = Equity - Used Margin
                available = equity - margin_used
                
                print(f"DEBUG MARGIN [{address[:6]}]: Equity: {equity} | Used: {margin_used} | Available: {available}")
                return max(0.0, available)
                
        except Exception as e:
            print(f"DEBUG BALANCE ERROR (state): {e}")
            
        # Fallback to balances if state fails
        try:
            data = self.get_perps_balances(address)
            if data and data.get("code") == 0:
                data_body = data.get("data", {})
                balances = data_body.get("balances", []) if isinstance(data_body, dict) else data_body
                if balances:
                    for b in balances:
                        asset = str(b.get("symbol", b.get("asset", ""))).upper()
                        if "USD" in asset or "USDT" in asset:
                            # If no available field, it's just wallet balance, which is risky
                            return float(b.get("available", 0))
        except: pass
        return 0.0

    def get_symbol_info(self, symbol_name: str) -> dict:
        try:
            resp = requests.get(f"{self.base_url}/markets/symbols", timeout=5).json()
            symbols = resp.get("data", [])
            for s in symbols:
                if s.get("name") == symbol_name:
                    return {
                        "id": int(s.get("id", 1)),
                        "name": s.get("name"),
                        "tickSize": float(s.get("tickSize", 1.0)),
                        "stepSize": float(s.get("stepSize", 0.00001))
                    }
        except Exception as e:
            print(f"DEBUG: Error in get_symbol_info: {e}")
        return {"id": 1, "name": symbol_name, "tickSize": 1.0, "stepSize": 0.00001}

    def get_symbol_info_by_id(self, symbol_id: int) -> dict:
        try:
            resp = requests.get(f"{self.base_url}/markets/symbols", timeout=5).json()
            symbols = resp.get("data", [])
            for s in symbols:
                if int(s.get("id", -1)) == int(symbol_id):
                    return {
                        "id": int(s.get("id", 1)),
                        "name": s.get("name"),
                        "tickSize": float(s.get("tickSize", 1.0)),
                        "stepSize": float(s.get("stepSize", 0.00001))
                    }
        except Exception as e:
            print(f"DEBUG: Error in get_symbol_info_by_id: {e}")
        return None

    def get_mark_price(self, symbol: str) -> str | None:
        try:
            url = f"{self.base_url}/markets/tickers"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for t in data.get("data", []):
                    if t.get("symbol") == symbol or t.get("s") == symbol: 
                        return t.get("markPrice") or t.get("mp") or t.get("p")
        except: pass
        return None

    def get_tickers(self):
        try:
            url = f"{self.base_url}/markets/tickers"
            resp = requests.get(url, timeout=5)
            return resp.json().get("data", [])
        except: return []

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 50):
        try:
            url = f"{self.base_url}/markets/{symbol}/klines"
            params = {"interval": interval, "limit": limit}
            print(f"DEBUG FETCH_KLINES URL: {url} with params {params}")
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            if data.get("code") == 0:
                k_list = data.get("data", [])
                print(f"DEBUG FETCH_KLINES SUCCESS: Found {len(k_list)} candles for {symbol}")
                return k_list
            print(f"DEBUG FETCH_KLINES ERROR: {data.get('msg')}")
            return []
        except Exception as e: 
            print(f"DEBUG FETCH_KLINES EXCEPTION: {e}")
            return []

    def get_markets(self) -> list:
        try:
            url = f"{self.base_url}/markets/tickers"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                tickers = data.get("data", [])
                
                # Sort by quoteVolume (qv or quoteVolume field) descending
                sorted_tickers = sorted(
                    tickers, 
                    key=lambda x: float(x.get("quoteVolume") or x.get("qv") or 0), 
                    reverse=True
                )
                
                symbols = [t.get("symbol") or t.get("s") for t in sorted_tickers]
                # Filter None and maintain order (unique)
                seen = set()
                return [x for x in symbols if x and not (x in seen or seen.add(x))]
        except: pass
        return ["BTC-USD", "ETH-USD", "SOL-USD"] # Fallback

    def get_perps_balances(self, address: str):
        try:
            url = f"{self.base_url}/accounts/{address}/balances"
            resp = requests.get(url, timeout=5)
            return resp.json()
        except: return None

    def get_perps_state(self, address: str):
        try:
            url = f"{self.base_url}/accounts/{address}/state"
            resp = requests.get(url, timeout=5)
            return resp.json()
        except: return None

    def get_perps_positions(self, address: str, account_id: int = None):
        try:
            url = f"{self.base_url}/accounts/{address}/positions"
            params = {}
            if account_id: params["accountID"] = account_id
            return requests.get(url, params=params, timeout=5).json()
        except: return None

    def get_perps_orders(self, address: str, account_id: int = None):
        try:
            url = f"{self.base_url}/accounts/{address}/orders"
            params = {}
            if account_id: params["accountID"] = account_id
            return requests.get(url, params=params, timeout=5).json()
        except: return None

    def execute_order(self, payload: dict, signature: str, nonce: int = None):
        n = nonce or int(time.time() * 1000)
        h = {"Content-Type": "application/json", "Accept": "application/json", "X-API-Sign": signature, "X-API-Nonce": str(n)}
        if self.api_key_name and not Config.SODEX_TESTNET: h["X-API-Key"] = str(self.api_key_name)
        return requests.post(f"{self.base_url}/trade/orders", data=json.dumps(payload.get("params", payload), separators=(',', ':')), headers=h, timeout=10).json()

    def execute_leverage(self, payload: dict, signature: str, nonce: int = None):
        n = nonce or int(time.time() * 1000)
        h = {"Content-Type": "application/json", "Accept": "application/json", "X-API-Sign": signature, "X-API-Nonce": str(n)}
        if not Config.SODEX_TESTNET: h["X-API-Key"] = str(self.api_key_name)
        return requests.post(f"{self.base_url}/trade/leverage", data=json.dumps(payload.get("params", payload), separators=(',', ':')), headers=h, timeout=10).json()
