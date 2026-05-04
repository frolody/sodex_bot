import requests
import os
from config import Config

class MarketIntelligence:
    def __init__(self):
        self.api_key = Config.SOSOVALUE_API_KEY
        self.base_url = "https://openapi.sosovalue.com/openapi/v1"

    def _get_headers(self):
        return {
            "x-soso-api-key": self.api_key,
            "accept": "application/json"
        }

    def get_etf_flows(self, symbol="BTC"):
        """
        Fetches the latest ETF net inflow/outflow data.
        Mandatory parameter: country_code (e.g., 'US')
        """
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
                    return {
                        "net_inflow": float(latest.get("total_net_inflow", 0)),
                        "cum_net_inflow": float(latest.get("cum_net_inflow", 0)),
                        "total_assets": float(latest.get("total_net_assets", 0)),
                        "date": latest.get("date")
                    }
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
