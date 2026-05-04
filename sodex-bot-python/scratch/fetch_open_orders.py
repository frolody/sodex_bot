import sys
import os
import json

sys.path.append(os.getcwd())
from config import Config
from sdk.client import SodexClient

def fetch_orders():
    client = SodexClient(is_spot=False)
    address = Config.MASTER_ADDRESS
    print(f"Fetching open orders for: {address}...")
    
    res = client.get_perps_orders(address, Config.SODEX_ACCOUNT_ID)
    print("RESPONSE JSON:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    fetch_orders()
