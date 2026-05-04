from sdk.client import SodexClient
from config import Config
from sdk.auth import SodexAuth
import json

def debug_orders():
    client = SodexClient()
    address = SodexAuth.recover_address(Config.SODEX_PRIVATE_KEY)
    print(f"Checking orders for {address} / Account {Config.SODEX_ACCOUNT_ID}")
    
    orders = client.get_perps_orders(address, Config.SODEX_ACCOUNT_ID)
    print(json.dumps(orders, indent=2))

if __name__ == "__main__":
    debug_orders()
