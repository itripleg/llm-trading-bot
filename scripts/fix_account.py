"""Try to fix/reset the account state"""
from trading.executor import HyperliquidExecutor
import json
import time

executor = HyperliquidExecutor(testnet=True)

print("=== Attempting to close any open positions ===")
# Try to close BTC position
try:
    result = executor.exchange.market_close("BTC")
    print(f"Close BTC result: {json.dumps(result, indent=2)}")
except Exception as e:
    print(f"Error closing BTC: {e}")

print("\nWaiting 2 seconds...")
time.sleep(2)

print("\n=== Check state after close ===")
state = executor.get_account_state()
print(f"Balance: ${state['account_value']:.2f}")
print(f"Positions: {len(state['positions'])}")

print("\n=== Now try a simple market order WITHOUT setting leverage ===")
print("Trading ETH (like the SDK example)")

# Trade ETH without explicit leverage setting
result = executor.exchange.market_open("ETH", True, 0.05, None, 0.01)
print(f"\nOrder result: {json.dumps(result, indent=2)}")

print("\nWaiting 2 seconds...")
time.sleep(2)

print("\n=== Check state ===")
state = executor.get_account_state()
print(f"Balance: ${state['account_value']:.2f}")
print(f"Margin Used: ${state['total_margin_used']:.2f}")
print(f"Positions: {len(state['positions'])}")

if state['positions']:
    print("\nSUCCESS! Position opened:")
    for asset_pos in state['positions']:
        pos = asset_pos.get('position', {})
        print(f"  {pos.get('coin')}: {pos.get('szi')} @ ${pos.get('entryPx')}")
else:
    print("\nFAILED - still no positions")
