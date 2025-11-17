"""Check raw Hyperliquid state using Info API directly"""
from trading.executor import HyperliquidExecutor
import json

executor = HyperliquidExecutor(testnet=True)

print("=== User State (raw from Info API) ===")
user_state = executor.info.user_state(executor.address)
print(json.dumps(user_state, indent=2))

print("\n=== Clearing House State ===")
clearinghouse_state = executor.info.clearinghouse_state(executor.address)
print(json.dumps(clearinghouse_state, indent=2))

print("\n=== Parsed Account State (our method) ===")
account_state = executor.get_account_state()
print(json.dumps(account_state, indent=2))
