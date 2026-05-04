import sys
import os
import json

sys.path.append(os.getcwd())
from config import Config
from sdk.client import SodexClient

def test_basic_order():
    print("--- SODEX BASIC ORDER TEST ---")
    client = SodexClient(is_spot=False)
    
    # Try a tiny market order
    res = client.place_order(
        account_id=Config.SODEX_ACCOUNT_ID,
        symbol_id=1, # BTC
        side=1, # LONG
        order_type=2, # MARKET
        quantity="0.0001",
        price="0", # Market doesn't need price
        reduce_only=False
    )
    
    print(f"RESPONSE: {json.dumps(res, indent=2)}")

if __name__ == "__main__":
    test_basic_order()
