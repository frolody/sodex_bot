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
        
        # Only try to recover address if private_key exists
        if not self.api_key_name and self.private_key:
            self.api_key_name = SodexAuth.recover_address(self.private_key)
        
        self.api_public_key = Config.SODEX_API_KEY
        
        domain = "testnet-gw" if Config.SODEX_TESTNET else "mainnet-gw"
        self.base_url = f"https://{domain}.sodex.dev/api/v1/perps"

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
            ("clOrdID",      f"{account_id}-{t}"),
            ("modifier",     int(modifier)),
            ("side",         int(side)),
            ("type",         int(order_type)),
            ("timeInForce",  int(3 if is_market else 1)),
            ("quantity",     str(quantity)),
            ("reduceOnly",   bool(reduce_only)),
            ("positionSide", int(position_side))
        ])

        # Insert price before quantity for Limit orders
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

    def place_order_with_tpsl(
        self,
        account_id:    int,
        symbol_id:     int,
        side:          int,
        order_type:    int,
        quantity:      str,
        price:         str,
        tp_price:      str,
        sl_price:      str,
        position_side: int  = 1,
    ) -> dict:
        t = int(time.time() * 1000)
        is_market = int(order_type) == 2
        
        parent = OrderedDict([
            ("clOrdID",      f"{account_id}-{t}-p"),
            ("modifier",     3), # BRACKET
            ("side",         int(side)),
            ("type",         int(order_type)),
            ("timeInForce",  3 if is_market else 1),
            ("quantity",     str(quantity)),
            ("reduceOnly",   False),
            ("positionSide", int(position_side))
        ])
        
        # Insert price before quantity for Limit orders
        if not is_market:
            # We need to recreate to insert at correct position
            new_parent = OrderedDict()
            for k, v in parent.items():
                if k == "quantity":
                    new_parent["price"] = str(price)
                new_parent[k] = v
            parent = new_parent

        tp = OrderedDict([
            ("clOrdID",      f"{account_id}-{t}-tp"),
            ("modifier",     4), # ATTACHED_STOP
            ("side",         2 if side == 1 else 1),
            ("type",         2), # MARKET
            ("timeInForce",  3), # IOC
            ("quantity",     str(quantity)),
            ("stopPrice",    str(tp_price)),
            ("stopType",     2), # TAKE_PROFIT
            ("triggerType",  2), # MARK_PRICE
            ("reduceOnly",   True),
            ("positionSide", int(position_side))
        ])

        sl = OrderedDict([
            ("clOrdID",      f"{account_id}-{t}-sl"),
            ("modifier",     4), # ATTACHED_STOP
            ("side",         2 if side == 1 else 1),
            ("type",         2), # MARKET
            ("timeInForce",  3), # IOC
            ("quantity",     str(quantity)),
            ("stopPrice",    str(sl_price)),
            ("stopType",     1), # STOP_LOSS
            ("triggerType",  2), # MARK_PRICE
            ("reduceOnly",   True),
            ("positionSide", int(position_side))
        ])

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("orders",    [parent, tp, sl])
        ])

        return self._post_trade("newOrder", params, nonce=t)

    def _post_trade(self, method: str, params: dict):
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

        # BEST KNOWN HEADER CONFIGURATION
        headers = {
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "X-API-Sign":    signature,
            "X-API-Nonce":   str(nonce),
        }
        
        if not Config.SODEX_TESTNET:
            headers["X-API-Key"] = str(self.api_key_name)
            headers["Authorization"] = f"Bearer {self.api_key_name}"

        url = f"{self.base_url}/trade/orders"
        json_body = json.dumps(params, separators=(',', ':'))
        
        try:
            print(f"DEBUG _POST_TRADE URL: {url}")
            print(f"DEBUG _POST_TRADE HEADERS: {json.dumps(headers, indent=2)}")
            print(f"DEBUG _POST_TRADE BODY: {json_body}")
            resp = requests.post(url, data=json_body, headers=headers, timeout=10)
            print(f"DEBUG _POST_TRADE RESP: {resp.status_code} - {resp.text}")
            return resp.json()
        except Exception as e:
            return {"code": -1, "error": f"Network Error: {str(e)}"}

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

    def get_markets(self) -> list:
        try:
            url = f"{self.base_url}/markets/tickers"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                tickers = data.get("data", [])
                
                # Sort by quoteVolume (qv or quoteVolume field) descending
                # This gives better liquidity info than base volume
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

    def get_balance(self, address: str):
        try:
            url = f"https://testnet-gw.sodex.dev/api/v1/spot/accounts/{address}/state"
            resp = requests.get(url, timeout=5)
            return resp.json()
        except: return {"error": "balance error"}

    def get_perps_balance(self, address: str):
        state = self.get_perps_state(address)
        if state and state.get("code") == 0:
            return float(state["data"].get("av", 0)) # Available margin
        return 0.0

    def get_perps_state(self, address: str):
        try:
            url = f"{self.base_url}/accounts/{address}/state"
            resp = requests.get(url, timeout=5)
            return resp.json()
        except: return None

    def get_perps_balances(self, address: str):
        try:
            url = f"{self.base_url}/accounts/{address}/balances"
            resp = requests.get(url, timeout=5)
            return resp.json()
        except: return None

    def get_perps_positions(self, address: str, account_id: int = None):
        try:
            url = f"{self.base_url}/accounts/{address}/positions"
            params = {}
            if account_id: params["accountID"] = account_id
            resp = requests.get(url, params=params, timeout=5)
            return resp.json()
        except: return None

    def get_perps_orders(self, address: str, account_id: int = None):
        try:
            url = f"{self.base_url}/accounts/{address}/orders"
            params = {}
            if account_id: params["accountID"] = account_id
            resp = requests.get(url, params=params, timeout=5)
            return resp.json()
        except: return None

    def cancel_orders(self, account_id: int, symbol_id: int, order_ids: list):
        if not order_ids: return
        
        cancel_items = []
        for oid in order_ids:
            cancel_items.append(OrderedDict([("orderID", int(oid))]))

        params = OrderedDict([
            ("accountID", int(account_id)),
            ("symbolID",  int(symbol_id)),
            ("cancel",    cancel_items)
        ])

        return self._delete_trade("trade/orders", params)

    def _delete_trade(self, path: str, params: dict):
        nonce = int(time.time() * 1000)
        signature = SodexAuth.create_signature(
            private_key=self.private_key,
            method="cancelOrder", # For Perps, cancelOrder is the method for DELETE
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
        
        if not Config.SODEX_TESTNET:
            headers["X-API-Key"] = str(self.api_key_name)
            headers["Authorization"] = f"Bearer {self.api_key_name}"

        url = f"{self.base_url}/{path}"
        json_body = json.dumps(params, separators=(',', ':'))
        
        try:
            resp = requests.delete(url, data=json_body, headers=headers, timeout=10)
            return resp.json()
        except:
            return {"code": -1, "error": "Network Error"}

    def place_perps_order(self, account_id, symbol_id=1, side=1, order_type=1,
                          quantity="0.01", price="75000", position_side=1, reduce_only=False):
        return self.place_order(account_id, symbol_id, side, order_type,
                                quantity, price, position_side, reduce_only)

    def execute_order(self, payload: dict, signature: str, nonce: int = None):
        """
        Executes an order that was signed externally (e.g. by a browser wallet)
        """
        if not nonce:
            # Try to extract nonce from payload if possible, or use current time
            nonce = int(time.time() * 1000)

        headers = {
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "X-API-Sign":    signature,
            "X-API-Nonce":   str(nonce),
        }
        
        if not Config.SODEX_TESTNET:
            headers["X-API-Key"] = str(self.api_key_name)
            headers["Authorization"] = f"Bearer {self.api_key_name}"

        url = f"{self.base_url}/trade/orders"
        json_body = json.dumps(payload.get("params", payload), separators=(',', ':'))
        
        try:
            print(f"DEBUG EXECUTE URL: {url}")
            print(f"DEBUG EXECUTE HEADERS: {json.dumps(headers, indent=2)}")
            print(f"DEBUG EXECUTE BODY: {json_body}")
            resp = requests.post(url, data=json_body, headers=headers, timeout=10)
            print(f"DEBUG EXECUTE RESP: {resp.status_code} - {resp.text}")
            return resp.json()
        except Exception as e:
            return {"code": -1, "error": f"Network Error: {str(e)}"}
    def execute_leverage(self, payload: dict, signature: str, nonce: int = None):
        """
        Updates leverage for a symbol (Signed Write)
        """
        if not nonce:
            nonce = int(time.time() * 1000)

        headers = {
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "X-API-Sign":    signature,
            "X-API-Nonce":   str(nonce),
        }
        
        if not Config.SODEX_TESTNET:
            headers["X-API-Key"] = str(self.api_key_name)
            headers["Authorization"] = f"Bearer {self.api_key_name}"

        url = f"{self.base_url}/trade/leverage"
        json_body = json.dumps(payload.get("params", payload), separators=(',', ':'))
        
        try:
            print(f"DEBUG LEVERAGE URL: {url}")
            print(f"DEBUG LEVERAGE BODY: {json_body}")
            resp = requests.post(url, data=json_body, headers=headers, timeout=10)
            print(f"DEBUG LEVERAGE RESP: {resp.status_code} - {resp.text}")
            return resp.json()
        except Exception as e:
            return {"code": -1, "error": f"Network Error: {str(e)}"}
