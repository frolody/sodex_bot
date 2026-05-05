import time
import json
import requests
from collections import OrderedDict
from config import Config
from sdk.auth import SodexAuth

class SodexClient:
    def __init__(self, is_spot=True, api_key_name=None, private_key=None):
        self.is_spot = is_spot
        self.private_key = private_key or Config.SODEX_PRIVATE_KEY
        self.chain_id = Config.SODEX_CHAIN_ID
        self.api_key_name = api_key_name or Config.SODEX_API_NAME
        
        if not self.api_key_name and self.private_key:
            self.api_key_name = SodexAuth.recover_address(self.private_key)
        
        self.api_public_key = Config.SODEX_API_KEY
        
        domain = "testnet-gw" if Config.SODEX_TESTNET else "mainnet-gw"
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
            print(f"DEBUG _POST_TRADE [{http_method}] URL: {url}")
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

    def update_position_tpsl(self, account_id: int, symbol_id: str, side: int = None, quantity: str = None, tp_price: str = None, sl_price: str = None):
        """
        Dynamically updates TP/SL for a position.
        Uses modifyOrder if orders exist, otherwise uses newOrder with modifier 2.
        """
        symbol_info = self.get_symbol_info(symbol_id)
        actual_symbol_id = symbol_info["id"]
        
        raw_orders = self.get_perps_orders(SodexAuth.recover_address(self.private_key), account_id)
        data = raw_orders.get("data", {}) if isinstance(raw_orders, dict) else {}
        existing_orders = data.get("orders", []) if isinstance(data, dict) else []
        
        print(f"DEBUG: Found {len(existing_orders)} total open orders.")
        
        tp_order = None
        sl_order = None
        
        modifies = []
        to_cancel = []
        for o in existing_orders:
            if not isinstance(o, dict): continue
            s = o.get("s") or o.get("symbol")
            if s != symbol_id: continue
            
            oid = o.get("i") or o.get("orderID")
            if oid: to_cancel.append(oid)
            
            st = o.get("st") or o.get("stopType")
            if st in [2, "TAKE_PROFIT"]: tp_order = o
            elif st in [1, "STOP_LOSS"]: sl_order = o

        if tp_order and tp_price:
            oid = tp_order.get("i") or tp_order.get("orderID")
            if oid:
                modifies.append({"orderID": int(oid), "stopPrice": str(tp_price)})
        if sl_order and sl_price:
            oid = sl_order.get("i") or sl_order.get("orderID")
            if oid:
                modifies.append({"orderID": int(oid), "stopPrice": str(sl_price)})

        if modifies:
            print(f">>>> SODEX: Modifying {len(modifies)} existing TP/SL orders...")
            res = self.modify_orders(account_id, actual_symbol_id, modifies)
            if res.get("code") == 0: return res
            print(f"MODIFY FAILED: {res.get('error') or res.get('msg')}. Cleaning up instead.")

        if to_cancel:
            print(f">>>> SODEX: Cleaning up {len(to_cancel)} old TP/SL orders...")
            self.cancel_orders(account_id, actual_symbol_id, to_cancel)
            time.sleep(0.5)

        # Fallback: Place new TP/SL
        # If quantity/side not provided, fetch from position
        if not side or not quantity:
            pos_data = self.get_perps_positions(SodexAuth.recover_address(self.private_key), account_id)
            positions = pos_data.get("data", []) if isinstance(pos_data, dict) else []
            target_pos = next((p for p in positions if (p.get("s") or p.get("symbol")) == symbol_id), None)
            
            if not target_pos:
                return {"code": -1, "msg": f"No open position found for {symbol_id}"}
                
            quantity = abs(float(target_pos.get("sz") or target_pos.get("size") or 0))
            side = 1 if float(target_pos.get("sz") or 0) > 0 else 2
        
        opp_side = 2 if int(side) == 1 else 1
        
        t = int(time.time() * 1000)
        final_res = {"code": 0, "msg": "No updates needed"}
        
        if tp_price:
            print(f">>>> SODEX: Placing new TP @ {tp_price}")
            tp_payload = OrderedDict([
                ("accountID", int(account_id)),
                ("symbolID",  int(actual_symbol_id)),
                ("orders", [OrderedDict([
                    ("clOrdID", f"{t}-tp"),
                    ("modifier", 2),
                    ("side", opp_side),
                    ("type", 2),
                    ("timeInForce", 3),
                    ("quantity", str(quantity)),
                    ("stopPrice", str(tp_price)),
                    ("stopType", 2),
                    ("triggerType", 2),
                    ("reduceOnly", True),
                    ("positionSide", 1)
                ])])
            ])
            final_res = self._post_trade("newOrder", tp_payload, nonce=t)
            time.sleep(0.2)
            
        if sl_price:
            t2 = int(time.time() * 1000) + 5
            print(f">>>> SODEX: Placing new SL @ {sl_price}")
            sl_payload = OrderedDict([
                ("accountID", int(account_id)),
                ("symbolID",  int(actual_symbol_id)),
                ("orders", [OrderedDict([
                    ("clOrdID", f"{t2}-sl"),
                    ("modifier", 2),
                    ("side", opp_side),
                    ("type", 2),
                    ("timeInForce", 3),
                    ("quantity", str(quantity)),
                    ("stopPrice", str(sl_price)),
                    ("stopType", 1),
                    ("triggerType", 2),
                    ("reduceOnly", True),
                    ("positionSide", 1)
                ])])
            ])
            final_res = self._post_trade("newOrder", sl_payload, nonce=t2)

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
        """
        # If leverage is provided, we could call set_leverage here if needed, 
        # but usually it's set before calling this.
        t = int(time.time() * 1000)
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
            tp_order = OrderedDict([
                ("clOrdID",      f"{t}-tp"),
                ("modifier",     4), # Attached
                ("side",         opp_side),
                ("type",         2), # Market/StopMarket
                ("timeInForce",  3), # IOC
                ("quantity",     str(quantity)),
                ("stopPrice",    str(tp_price)),
                ("stopType",     2), # TP
                ("triggerType",  2), # Mark Price
                ("reduceOnly",   True),
                ("positionSide", 1)
            ])
            orders.append(tp_order)

        # 3. Stop Loss (Modifier 4)
        if sl_price:
            sl_order = OrderedDict([
                ("clOrdID",      f"{t}-sl"),
                ("modifier",     4),
                ("side",         opp_side),
                ("type",         2),
                ("timeInForce",  3),
                ("quantity",     str(quantity)),
                ("stopPrice",    str(sl_price)),
                ("stopType",     1), # SL
                ("triggerType",  2),
                ("reduceOnly",   True),
                ("positionSide", 1)
            ])
            orders.append(sl_order)

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders",    orders)
        ])

        return self._post_trade("newOrder", params, nonce=t)

    def get_perps_balance(self, address: str) -> float:
        try:
            data = self.get_perps_balances(address)
            if data and data.get("code") == 0:
                balances = data.get("data", [])
                if balances:
                    return float(balances[0].get("balance", 0))
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
                        "tickSize": float(s.get("tickSize", 1.0)),
                        "stepSize": float(s.get("stepSize", 0.00001))
                    }
        except Exception as e:
            print(f"DEBUG: Error in get_symbol_info: {e}")
        return {"id": 1, "tickSize": 1.0, "stepSize": 0.00001}

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
