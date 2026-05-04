import requests
from config import Config

class NewsAggregator:
    def __init__(self):
        self.cryptopanic_key = Config.CRYPTO_PANIC_API_KEY
        self.sosovalue_key = Config.SOSOVALUE_API_KEY
        self.cp_url = "https://cryptopanic.com/api/v1/posts/"
        self.soso_url = "https://api.sosovalue.com/v1/news" # Placeholder URL

    def fetch_latest_news(self, currency="BTC", limit=5):
        """
        Fetches news from SoSoValue (Primary) and CryptoPanic (Fallback)
        """
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
                        print("DEBUG NEWS for {currency}: SoSoValue Hot News returned empty. Trying News List...")
                
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

        # 2. Fallback to CryptoPanic if SoSoValue fails or returns nothing
        if not news_results and self.cryptopanic_key:
            try:
                # Attempt 1: Specific Currency
                print(f"DEBUG NEWS: Fetching from CryptoPanic for {currency}...")
                params = {
                    "auth_token": self.cryptopanic_key,
                    "currencies": currency,
                    "filter": "hot", 
                    "kind": "news"
                }
                response = requests.get(self.cp_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        print(f"DEBUG NEWS: Fetched {len(results)} posts from CryptoPanic for {currency}")
                        for item in results[:limit]:
                            news_results.append({"title": item.get("title")})
                    else:
                        print(f"DEBUG NEWS: CryptoPanic returned empty for {currency}. Trying general hot news...")
                        # Attempt 2: General Hot News
                        params.pop("currencies")
                        response = requests.get(self.cp_url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            results = data.get("results", [])
                            print(f"DEBUG NEWS: Fetched {len(results)} general hot posts from CryptoPanic")
                            for item in results[:limit]:
                                news_results.append({"title": item.get("title")})
            except Exception as e:
                print(f"CryptoPanic Fetch Error: {e}")
        
        return news_results
