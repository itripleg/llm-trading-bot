"""Check balances on both accounts"""
from trading.executor import HyperliquidExecutor
from hyperliquid.info import Info
from hyperliquid.utils import constants

executor = HyperliquidExecutor(testnet=True)

print("=== Account Setup ===")
print(f"Main Account: {executor.address}")
print(f"API Wallet: {executor.account.address}")

print("\n=== Main Account Balance ===")
main_state = executor.info.user_state(executor.address)
main_balance = float(main_state['marginSummary']['accountValue'])
main_positions = len(main_state['assetPositions'])
print(f"Balance: ${main_balance:.2f}")
print(f"Positions: {main_positions}")

print("\n=== API Wallet Balance (should be $0) ===")
api_state = executor.info.user_state(executor.account.address)
api_balance = float(api_state['marginSummary']['accountValue'])
api_positions = len(api_state['assetPositions'])
print(f"Balance: ${api_balance:.2f}")
print(f"Positions: {api_positions}")

if api_balance > 0:
    print("\n⚠️  WARNING: API wallet has funds!")
    print(f"   You should transfer ${api_balance:.2f} from API wallet to main account")
    print("   API wallet doesn't need funds - it just signs orders")
else:
    print("\n✓ Correct setup! API wallet has no funds")

print("\n=== Summary ===")
print(f"Total funds: ${main_balance + api_balance:.2f}")
print(f"  Main: ${main_balance:.2f}")
print(f"  API:  ${api_balance:.2f}")
