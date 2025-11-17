from trading.executor import HyperliquidExecutor

e = HyperliquidExecutor(testnet=True)
s = e.info.user_state(e.address)

account_value = float(s["marginSummary"]["accountValue"])
withdrawable = float(s["withdrawable"])
used = account_value - withdrawable

print(f'Account Value: ${account_value:.2f}')
print(f'Withdrawable: ${withdrawable:.2f}')
print(f'Used (locked in positions/orders): ${used:.2f}')

if used > 0:
    print("\n*** MARGIN IS BEING USED - positions may exist but not showing! ***")
else:
    print("\nNo margin locked - confirms nothing is actually trading")
