"""Test script to manually place a small trade and see full API response"""
from trading.executor import HyperliquidExecutor
import json

print("Initializing executor...")
executor = HyperliquidExecutor(testnet=True)

print("\n=== Account State BEFORE ===")
state_before = executor.get_account_state()
print(f"Balance: ${state_before['account_value']:.2f}")
print(f"Positions: {len(state_before['positions'])}")

print("\n=== Attempting Small Trade ===")
print("Trade: $50 margin @ 2x leverage = $100 notional")
print("Coin: BTC")
print("Type: LONG (buy)")

# Place a small test order
result = executor.market_open_usd(
    coin="BTC/USDC:USDC",
    is_buy=True,
    usd_amount=50.0,  # $50 margin
    current_price=95000.0,  # Approximate price
    leverage=2,  # 2x leverage
    slippage=0.05
)

print("\n=== API Response ===")
print(json.dumps(result, indent=2))

print("\n=== Account State AFTER (immediate) ===")
state_after = executor.get_account_state()
print(f"Balance: ${state_after['account_value']:.2f}")
print(f"Margin Used: ${state_after['total_margin_used']:.2f}")
print(f"Positions: {len(state_after['positions'])}")

if state_after['positions']:
    for asset_pos in state_after['positions']:
        pos = asset_pos.get('position', {})
        print(f"\nPosition: {pos.get('coin')}")
        print(f"  Size: {pos.get('szi')}")
        print(f"  Entry: ${pos.get('entryPx')}")
        print(f"  Margin: ${pos.get('marginUsed')}")
        print(f"  Leverage: {pos.get('leverage', {}).get('value', 'N/A')}")
