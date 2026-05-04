import requests
import json

def check_symbols():
    url = "https://testnet-gw.sodex.dev/api/v1/perps/markets/symbols"
    resp = requests.get(url).json()
    print(json.dumps(resp, indent=2))

if __name__ == "__main__":
    check_symbols()
