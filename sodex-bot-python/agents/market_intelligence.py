import requests
import os
from config import Config
import time

class MarketIntelligence:
    def __init__(self):
        self.api_key = Config.SOSOVALUE_API_KEY
        self.base_url = "https://openapi.sosovalue.com/openapi/v1"
        self._cache = {} # Format: {symbol: (timestamp, data)}
        self._cache_expiry = 3600 # 1 hour

    def _get_headers(self):
        return {
            "x-soso-api-key": self.api_key,
            "accept": "application/json"
        }

    def get_etf_flows(self, symbol="BTC"):
        """
        Fetches the latest ETF net inflow/outflow data with 1-hour caching.
        """
        symbol = symbol.upper()
        
        # Check Cache
        now = time.time()
        if symbol in self._cache:
            ts, data = self._cache[symbol]
            if now - ts < self._cache_expiry:
                print(f"DEBUG SOSO ETF: Using Cached Data for {symbol} (Age: {int(now-ts)}s)")
                return data

        if not self.api_key:
            return None
        
        # SosoValue only supports specific symbols for ETF
        ALLOWED_ETF_SYMBOLS = ["BTC", "SOL", "AVAX", "XRP", "ETH", "DOT", "DOGE", "LINK", "LTC", "HBAR"]
        if symbol.upper() not in ALLOWED_ETF_SYMBOLS:
            print(f"DEBUG SOSO ETF: Skipping unsupported symbol {symbol}")
            return None
        
        try:
            url = f"{self.base_url}/etfs/summary-history"
            headers = self._get_headers()
            # Adding required country_code parameter
            params = {
                "symbol": symbol,
                "country_code": "US" 
            }
            
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"DEBUG SOSO ETF: Status {resp.status_code} for {symbol}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"DEBUG SOSO ETF DATA: {str(data)[:200]}...")
                history = data.get("data", [])
                if history:
                    latest = history[0]
                    result = {
                        "net_inflow": float(latest.get("total_net_inflow", 0)),
                        "cum_net_inflow": float(latest.get("cum_net_inflow", 0)),
                        "total_assets": float(latest.get("total_net_assets", 0)),
                        "date": latest.get("date")
                    }
                    # Update Cache
                    self._cache[symbol] = (time.time(), result)
                    return result
            else:
                print(f"DEBUG SOSO ETF ERROR: {resp.text}")
        except Exception as e:
            print(f"Error fetching ETF flows: {e}")
        return None

    def get_market_indicators(self):
        """
        Fetches general market indicators. 
        Note: Removed non-existent Fear & Greed and global snapshot.
        """
        # Placeholder for future valid indicators
        return {}

    def get_comprehensive_intel(self, symbol="BTC"):
        """
        Combines news sentiment, ETF flows, and market health.
        """
        return {
            "etf": self.get_etf_flows(symbol),
            "indicators": self.get_market_indicators()
        }
