import sys
import os
import json
from decimal import Decimal

# Add current dir to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv() # Load from project root

from config import Config
from sdk.client import SodexClient

def test_tpsl_update():
    print("--- SODEX TP/SL UPDATE TEST ---")
    
    print(f"DEBUG: Private Key loaded: {Config.SODEX_PRIVATE_KEY[:10]}...")
    
    # Rule 6: Don't send X-API-Key on testnet
    client = SodexClient(
        is_spot=False,
        api_key_name=None
    )
    
    # 1. Fetch Positions
    address = Config.MASTER_ADDRESS
    print(f"Checking positions for: {address}...")
    
    state = client.get_perps_state(address)
    if not state or state.get("code") != 0:
        print(f"Error fetching state: {state}")
        return

    positions = state.get("data", {}).get("P", [])
    active_pos = None
    for p in positions:
        if float(p.get("sz", 0)) != 0:
            active_pos = p
            break
            
    if not active_pos:
        print("❌ NO ACTIVE POSITION FOUND. Please open a position manually first (LONG or SHORT).")
        return

    symbol = active_pos.get('s') or active_pos.get('symbol')
    # Detection of side: positive sz = LONG (1), negative sz = SHORT (2)
    raw_size = float(active_pos.get('sz') or 0)
    side = 1 if raw_size > 0 else 2
    size = abs(raw_size)
    entry = float(active_pos.get('ep') or active_pos.get('avgEntryPrice') or 0)
    
    print(f"DEBUG RAW POS: {active_pos}")
    print(f"FOUND POSITION: {symbol} | Side: {'LONG' if side==1 else 'SHORT'} | Size: {size} | Entry: {entry}")

    # 2. Get Current Mark Price
    mark_p = float(client.get_mark_price(symbol) or entry)
    print(f"Current Mark Price: {mark_p}")

    # 3. Calculate dummy TP/SL (2% away for testing)
    if side == 1: # LONG
        new_tp = int(mark_p * 1.02)
        new_sl = int(mark_p * 0.98)
    else: # SHORT
        new_tp = int(mark_p * 0.98)
        new_sl = int(mark_p * 1.02)
        
    print(f"Proposed Update -> TP: {new_tp} | SL: {new_sl}")

    # 4. Execute Update
    print(f"\nTriggering TP/SL Update for {symbol}...")
    res = client.update_position_tpsl(
        account_id=Config.SODEX_ACCOUNT_ID,
        symbol_id=symbol, # Pass "BTC-USD" string
        side=side,
        quantity=size,
        tp_price=str(new_tp),
        sl_price=str(new_sl)
    )
    
    print(f"RESPONSE: {json.dumps(res, indent=2)}")
    
    if res.get("code") == 0:
        print("\nSUCCESS! TP/SL Added on SoDEX.")
        print("Check your dashboard to verify the new open orders.")
    else:
        print("\nFAILED. Check the error message above.")

if __name__ == "__main__":
    test_tpsl_update()
