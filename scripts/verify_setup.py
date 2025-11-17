"""Verify our testnet and wallet setup"""
from trading.executor import HyperliquidExecutor
from config.settings import settings
from hyperliquid.utils import constants

print("=== Configuration Check ===")
print(f"Private Key: {settings.hyperliquid_wallet_private_key[:10]}...")
print(f"Account Address from .env: {settings.hyperliquid_account_address or 'None (using derived)'}")
print(f"Testnet setting: {settings.hyperliquid_testnet}")

print("\n=== Executor Setup ===")
executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)
print(f"Using testnet: {executor.testnet}")
print(f"Base URL: {executor.base_url}")
print(f"Expected testnet URL: {constants.TESTNET_API_URL}")
print(f"Expected mainnet URL: {constants.MAINNET_API_URL}")

print(f"\nWallet address (derived): {executor.account.address}")
print(f"Trading address (actual): {executor.address}")

print("\n=== URL Match Check ===")
if executor.base_url == constants.TESTNET_API_URL:
    print("✓ Confirmed using TESTNET")
elif executor.base_url == constants.MAINNET_API_URL:
    print("✗ WARNING: Using MAINNET despite testnet=True!")
else:
    print(f"? Unknown URL: {executor.base_url}")

print("\n=== Account Address Logic ===")
if settings.hyperliquid_account_address:
    print(f"Using separate account address: {settings.hyperliquid_account_address}")
    print("This is API wallet pattern - trading on behalf of main account")
else:
    print("Using wallet directly (derived address from private key)")
    print("This is personal wallet pattern")
