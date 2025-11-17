"""Check current balance from Hyperliquid and database"""
from trading.executor import HyperliquidExecutor
from run_analysis_bot import get_current_account_state
import sqlite3

print("=== Current Hyperliquid Balance ===")
executor = HyperliquidExecutor(testnet=True)
state = get_current_account_state(executor=executor, account=None, current_prices={}, is_live=True)
print(f"Balance: ${state['balance']:.2f}")
print(f"Positions: {state['num_positions']}")

print("\n=== Database Account State ===")
conn = sqlite3.connect('data/trading_bot_live.db')
cursor = conn.cursor()
cursor.execute('SELECT balance_usd, equity_usd, timestamp FROM account_state ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()
if row:
    print(f"Balance: ${row[0]:.2f}")
    print(f"Equity: ${row[1]:.2f}")
    print(f"Timestamp: {row[2]}")
else:
    print("No account state in database")

print("\n=== Issue ===")
if row and abs(row[0] - state['balance']) > 1:
    print(f"MISMATCH! Database shows ${row[0]:.2f} but Hyperliquid shows ${state['balance']:.2f}")
    print("The bot needs to save updated state to database")
else:
    print("Balance looks correct")
