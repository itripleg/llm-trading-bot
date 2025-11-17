"""Check user fills/trade history"""
from trading.executor import HyperliquidExecutor
import json

executor = HyperliquidExecutor(testnet=True)

print("=== Recent User Fills ===")
try:
    fills = executor.info.user_fills(executor.address)
    print(f"Found {len(fills)} fills")

    if fills:
        print("\nMost recent fills:")
        for fill in fills[:10]:  # Show last 10
            print(json.dumps(fill, indent=2))
    else:
        print("No fills found")
except Exception as e:
    print(f"Error getting fills: {e}")
