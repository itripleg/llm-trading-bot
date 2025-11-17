from trading.executor import HyperliquidExecutor
import json

e = HyperliquidExecutor(testnet=True)
s = e.get_account_state()

print(f'Balance: ${s["account_value"]:.2f}')
print(f'Margin Used: ${s["total_margin_used"]:.2f}')
print(f'Positions: {len(s["positions"])}')

if s["positions"]:
    print("\nOpen Positions:")
    for asset_pos in s["positions"]:
        pos = asset_pos.get("position", {})
        print(f"  {pos.get('coin')}: size={pos.get('szi')}, entry=${pos.get('entryPx')}, margin=${pos.get('marginUsed')}")

print(f'\nRaw state:')
print(json.dumps(s, indent=2))
