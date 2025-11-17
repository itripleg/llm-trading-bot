"""Transfer funds from API wallet to main account"""
from trading.executor import HyperliquidExecutor

executor = HyperliquidExecutor(testnet=True)

print("=== Current Balances ===")
main_state = executor.info.user_state(executor.address)
api_state = executor.info.user_state(executor.account.address)

main_balance = float(main_state['marginSummary']['accountValue'])
api_balance = float(api_state['marginSummary']['accountValue'])

print(f"Main Account: ${main_balance:.2f}")
print(f"API Wallet:   ${api_balance:.2f}")
print(f"Total:        ${main_balance + api_balance:.2f}")

if api_balance <= 0:
    print("\nAPI wallet already empty - nothing to transfer!")
    exit(0)

print(f"\n=== Transfer Plan ===")
print(f"Transfer ${api_balance:.2f} from API wallet to main account")
print(f"After transfer:")
print(f"  Main: ${main_balance + api_balance:.2f}")
print(f"  API:  $0.00")

print("\nInitiating transfer...")
# Note: The API wallet signs this, sending TO the main account
# usd_transfer(amount, destination_address)
result = executor.exchange.usd_transfer(api_balance, executor.address)

print(f"\nTransfer result: {result}")
print("\nChecking new balances...")

import time
time.sleep(2)

new_main_state = executor.info.user_state(executor.address)
new_api_state = executor.info.user_state(executor.account.address)

new_main_balance = float(new_main_state['marginSummary']['accountValue'])
new_api_balance = float(new_api_state['marginSummary']['accountValue'])

print(f"\nNew balances:")
print(f"Main Account: ${new_main_balance:.2f}")
print(f"API Wallet:   ${new_api_balance:.2f}")
print(f"Total:        ${new_main_balance + new_api_balance:.2f}")
