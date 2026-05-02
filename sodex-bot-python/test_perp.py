import asyncio
from config import Config
from sdk.client import SodexClient

async def test_order():
    Config.validate()
    print("Testing perp order on testnet...")
    client = SodexClient()
    
    response = client.place_perps_order(
        account_id=Config.SODEX_ACCOUNT_ID,
        symbol_id=1, # BTC-PERP
        side=1, # LONG
        order_type=1, # LIMIT
        quantity="0.0002",
        price="75000",
        position_side=1
    )
    print("Response:", response)

if __name__ == "__main__":
    asyncio.run(test_order())
