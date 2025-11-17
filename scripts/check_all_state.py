"""Check ALL state information"""
from trading.executor import HyperliquidExecutor
import json

executor = HyperliquidExecutor(testnet=True)

print("=== FULL User State ===")
state = executor.info.user_state(executor.address)
print(json.dumps(state, indent=2))

print("\n\n=== Open Orders ===")
try:
    open_orders = executor.info.open_orders(executor.address)
    print(json.dumps(open_orders, indent=2))
except Exception as e:
    print(f"Error getting open orders: {e}")

print("\n\n=== All Mids (Current Prices) ===")
try:
    mids = executor.info.all_mids()
    btc_price = mids.get('BTC', 'N/A')
    print(f"BTC Price: ${btc_price}")
except Exception as e:
    print(f"Error getting prices: {e}")

print("\n\n=== Meta Info ===")
try:
    meta = executor.info.meta()
    btc_info = [asset for asset in meta.get('universe', []) if asset.get('name') == 'BTC']
    print(f"BTC Info: {json.dumps(btc_info, indent=2)}")
except Exception as e:
    print(f"Error getting meta: {e}")
