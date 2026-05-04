import requests
import json

base_url_no_perps = "https://testnet-gw.sodex.dev/api/v1"
base_url_perps = "https://testnet-gw.sodex.dev/api/v1/perps"

def test_klines(base, symbol):
    print(f"--- TESTING KLINES FOR {symbol} on {base} ---")
    url = f"{base}/markets/klines"
    params = {"symbol": symbol, "interval": "15m", "limit": 5}
    try:
        resp = requests.get(url, params=params, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Items: {len(data.get('data', []))}")
            if data.get('data'):
                print(f"Sample: {data['data'][0]}")
        else:
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_klines(base_url_no_perps, "BTC-USD")
    test_klines(base_url_perps, "BTC-USD")
    test_klines(base_url_no_perps.replace("api/v1", "api/v2"), "BTC-USD")
