"""Test if isolated margin works differently"""
from trading.executor import HyperliquidExecutor
import json
import time

print("Initializing executor...")
executor = HyperliquidExecutor(testnet=True)

print("\n=== Testing ISOLATED margin ===")
# Set leverage with isolated margin
result = executor.set_leverage("BTC", 2, is_cross=False)
print(f"Set isolated leverage: {result}")

print("\nPlacing order with isolated margin...")
result = executor.market_open_usd(
    coin="BTC/USDC:USDC",
    is_buy=True,
    usd_amount=50.0,
    current_price=95000.0,
    leverage=2,
    slippage=0.05
)

print("\nAPI Response:")
print(json.dumps(result, indent=2))

print("\nWaiting 2 seconds...")
time.sleep(2)

print("\n=== Account State ===")
state = executor.get_account_state()
print(f"Balance: ${state['account_value']:.2f}")
print(f"Margin Used: ${state['total_margin_used']:.2f}")
print(f"Positions: {len(state['positions'])}")

if state['positions']:
    print("\nFound positions!")
    for asset_pos in state['positions']:
        pos = asset_pos.get('position', {})
        print(f"  {pos.get('coin')}: {pos.get('szi')} @ ${pos.get('entryPx')}")
else:
    print("\nNo positions found - testnet may be broken")
