import os
import requests
from config import Config
from sdk.auth import SodexAuth

def check():
    addr = SodexAuth.recover_address(Config.SODEX_PRIVATE_KEY)
    print(f"Checking address from .env private key: {addr}")
    
    # Try Spot state first
    url = f"https://testnet-gw.sodex.dev/api/v1/spot/accounts/{addr}/state"
    res = requests.get(url).json()
    print(f"Account Info: {res}")

if __name__ == "__main__":
    check()
