import sys
import os
from dotenv import load_dotenv

# Add current dir to path
sys.path.append(os.getcwd())
load_dotenv()

from sdk.client import SodexClient

def test_klines():
    print("--- TESTING GET_KLINES ---")
    client = SodexClient(is_spot=False)
    print(f"Checking if get_klines exists: {hasattr(client, 'get_klines')}")
    try:
        data = client.get_klines("BTC-USD", limit=5)
        print(f"Data received: {len(data)} items")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_klines()
