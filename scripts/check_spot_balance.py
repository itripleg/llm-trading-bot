"""Check if USDC is in spot vs perp"""
from trading.executor import HyperliquidExecutor
import json

executor = HyperliquidExecutor(testnet=True)

print("=== Perp Account State ===")
perp_state = executor.info.user_state(executor.address)
print(f"Perp Balance: ${perp_state['marginSummary']['accountValue']}")

print("\n=== Spot Account State ===")
spot_state = executor.info.spot_user_state(executor.address)
print(json.dumps(spot_state, indent=2))

if spot_state.get('balances'):
    print("\nSpot Balances Found:")
    for balance in spot_state['balances']:
        print(f"  {balance['coin']}: {balance['hold']} (available: {balance['total']})")

    print("\n*** You may need to transfer USDC from SPOT to PERP! ***")
    print("Command: executor.exchange.spot_to_perp(amount, False)")
else:
    print("\nNo spot balances - funds already in perp")
