import sys
import os
import json
import time
from dotenv import load_dotenv

# Add current dir to path
sys.path.append(os.getcwd())
load_dotenv()

from config import Config
from sdk.client import SodexClient
from sdk.auth import SodexAuth

def test_close_position():
    print("--- SODEX CLOSE POSITION TEST ---")
    
    client = SodexClient(is_spot=False, api_key_name=None)
    address = Config.MASTER_ADDRESS
    account_id = Config.SODEX_ACCOUNT_ID
    
    # 1. Fetch current position
    print(f"Fetching positions for {address}...")
    state = client.get_perps_state(address)
    positions = state.get("data", {}).get("P", [])
    
    target_pos = None
    for p in positions:
        if float(p.get("sz", 0)) != 0:
            target_pos = p
            break
            
    if not target_pos:
        print("❌ NO OPEN POSITION FOUND to close.")
        return

    symbol = target_pos.get('s') or target_pos.get('symbol')
    raw_size = float(target_pos.get('sz') or 0)
    side = 1 if raw_size > 0 else 2
    size = abs(raw_size)
    
    print(f"FOUND POSITION: {symbol} | Side: {'LONG' if side==1 else 'SHORT'} | Size: {size}")
    
    # 2. To close, send opposite side
    opp_side = 2 if side == 1 else 1
    print(f"\n>>>> SENDING CLOSE ORDER: {symbol} | Side: {'SELL' if opp_side==2 else 'BUY'} | Size: {size}")
    
    # Get symbol info for ID
    sym_info = client.get_symbol_info(symbol)
    symbol_id = sym_info['id']
    
    # 3. Create Market Close Order (reduceOnly=True, modifier=1)
    from collections import OrderedDict
    t = int(time.time() * 1000)
    
    order = OrderedDict([
        ("clOrdID",     f"{t}-close"),
        ("modifier",    1), # NORMAL
        ("side",        opp_side),
        ("type",        2), # MARKET
        ("timeInForce", 3), # IOC/GTC for Market
        ("quantity",    str(size)),
        ("reduceOnly",  True),
        ("positionSide", 1) # BOTH/LONG
    ])
    
    payload = OrderedDict([
        ("accountID", int(account_id)),
        ("symbolID",  int(symbol_id)),
        ("orders",    [order])
    ])
    
    res = client._post_trade("newOrder", payload, nonce=t)
    print(f"\nRESPONSE: {json.dumps(res, indent=2)}")
    
    if res.get("code") == 0:
        print("\n✅ POSITION CLOSED SUCCESSFULLY!")
    else:
        print("\n❌ FAILED TO CLOSE POSITION.")

if __name__ == "__main__":
    test_close_position()
