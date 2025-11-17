"""Quick script to check Hyperliquid wallet balance"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from trading.executor import HyperliquidExecutor

# Initialize executor
print("Initializing Hyperliquid executor...")
print(f"Testnet: {settings.hyperliquid_testnet}")
executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)

# Show wallet info
print(f"\nWallet Address: {executor.address}")
print(f"Private Key (first 10 chars): {settings.hyperliquid_wallet_private_key[:10]}...")

# Query account state
print("\nQuerying account state from Hyperliquid...")
state = executor.get_account_state()

# Show balance
print(f"\nAccount Value: ${state.get('account_value', 0):.2f}")
print(f"Withdrawable: ${state.get('withdrawable', 0):.2f}")

# Show positions if any
positions = state.get('positions', [])
print(f"\nOpen Positions: {len(positions)}")
if positions:
    for asset_pos in positions:
        pos = asset_pos.get('position', {})
        print(f"  {pos.get('coin')}: {pos.get('szi')} @ ${pos.get('entryPx')}")

# Show raw response for debugging
print("\n--- RAW RESPONSE ---")
import json
print(json.dumps(state, indent=2))
