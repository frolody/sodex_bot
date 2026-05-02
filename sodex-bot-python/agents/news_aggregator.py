import requests
from config import Config

class NewsAggregator:
    def __init__(self):
        self.cryptopanic_key = Config.CRYPTO_PANIC_API_KEY
        self.sosovalue_key = Config.SOSOVALUE_API_KEY
        self.cp_url = "https://cryptopanic.com/api/v1/posts/"
        self.soso_url = "https://api.sosovalue.com/v1/news/list" # Placeholder URL

    def fetch_latest_news(self, currency="BTC", limit=5):
        """Fetches news from multiple sources (SoSoValue preferred)."""
        news_results = []
        
        # 1. Try SoSoValue (Preferred as per new roadmap)
        if self.sosovalue_key:
            try:
                # Based on typical API structures
                headers = {"Authorization": f"Bearer {self.sosovalue_key}"}
                params = {"symbol": currency, "pageSize": limit}
                resp = requests.get(self.soso_url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # Mapping generic 'title' key
                    for item in data.get("data", [])[:limit]:
                        news_results.append({"title": item.get("title") or item.get("content")})
            except Exception as e:
                print(f"SoSoValue Fetch Error: {e}")

        # 2. Fallback to CryptoPanic
        if not news_results and self.cryptopanic_key:
            try:
                params = {
                    "auth_token": self.cryptopanic_key,
                    "currencies": currency,
                    "filter": "hot", 
                    "kind": "news"
                }
                response = requests.get(self.cp_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("results", [])[:limit]:
                        news_results.append({"title": item.get("title")})
            except Exception as e:
                print(f"CryptoPanic Fetch Error: {e}")
        
        return news_results
