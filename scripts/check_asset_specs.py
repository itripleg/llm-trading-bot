"""Check Hyperliquid asset specifications for size precision"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from trading.executor import HyperliquidExecutor

# Initialize executor
executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)

# Get metadata
print("Querying Hyperliquid asset metadata...")
meta = executor.info.meta()

# Find BTC specs
print("\n=== BTC Asset Specs ===")
for asset in meta.get('universe', []):
    if asset.get('name') == 'BTC':
        print(f"Asset: {asset}")
        print(f"\nSize Decimals: {asset.get('szDecimals')}")
        print(f"Max Leverage: {asset.get('maxLeverage')}")
        print(f"Only Isolated: {asset.get('onlyIsolated')}")
        break

# Test position sizes
test_sizes = [0.001, 0.0018, 0.002, 0.01]
print("\n=== Testing Position Sizes ===")
for size in test_sizes:
    print(f"{size} BTC = ${size * 95400:.2f} notional @ $95,400")
