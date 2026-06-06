import requests
from config import Config

class NewsAggregator:
    def __init__(self):
        self.sosovalue_key = Config.SOSOVALUE_API_KEY
        self.soso_url = "https://api.sosovalue.com/v1/news" # Placeholder URL
        self._cache = {} # Format: {currency: (timestamp, results)}
        self._cache_expiry = 900 # 15 minutes

    def fetch_latest_news(self, currency="BTC", limit=5):
        """
        Fetches news from SoSoValue with 15-min caching.
        """
        import time
        currency = currency.upper()
        
        # Check Cache
        now = time.time()
        if currency in self._cache:
            ts, results = self._cache[currency]
            if now - ts < self._cache_expiry:
                print(f"DEBUG NEWS: Using Cached News for {currency} (Age: {int(now-ts)}s)")
                return results
        news_results = []
        
        # 1. Try SoSoValue (Official Featured News)
        if self.sosovalue_key:
            try:
                headers = {
                    "x-soso-api-key": self.sosovalue_key,
                    "accept": "application/json"
                }
                # Attempt 1: Featured/Hot News
                print(f"DEBUG NEWS: Fetching from SoSoValue Hot News...")
                url_hot = "https://openapi.sosovalue.com/openapi/v1/news/search" 
                resp = requests.get(url_hot, headers=headers, params={"pageSize": limit, "keyword":currency}, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    # Response structure: data -> list
                    data_obj = data.get("data", {})
                    results = data_obj.get("list", []) if isinstance(data_obj, dict) else []
                    
                    if results:
                        print(f"DEBUG NEWS for {currency}: Fetched {len(results)} hot posts from SoSoValue")
                        for item in results[:limit]:
                            title = item.get("title") or item.get("content", "")
                            news_results.append({"title": title[:200]})
                    else:
                        print(f"DEBUG NEWS for {currency}: SoSoValue Hot News returned empty. Trying News List...")
                
                # Attempt 2: Generic News List if hot was empty
                if not news_results:
                    url_list = "https://openapi.sosovalue.com/openapi/v1/news/search"
                    # Try with symbol
                    resp = requests.get(url_list, headers=headers, params={"pageSize": limit}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        data_obj = data.get("data", {})
                        results = data_obj.get("list", []) if isinstance(data_obj, dict) else []
                        
                        if results:
                            print(f"DEBUG NEWS: Fetched {len(results)} news items from SoSoValue List for {currency}")
                            for item in results[:limit]:
                                title = item.get("title") or item.get("content", "")
                                news_results.append({"title": title[:200]})
            except Exception as e:
                print(f"SoSoValue Fetch Error: {e}")
        
        if news_results:
            import time
            self._cache[currency] = (time.time(), news_results)
            
        return news_results
