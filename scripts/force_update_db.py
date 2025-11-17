"""Force update database with current Hyperliquid state"""
from trading.executor import HyperliquidExecutor
from run_analysis_bot import get_current_account_state
from web.database import save_account_state, set_database_path
from config.settings import settings

# Use correct database
db_mode = "live" if settings.is_live_trading() else "paper"
set_database_path(db_mode)
print(f"Using database: trading_bot_{db_mode}.db\n")

print("=== Querying Current State ===")
executor = HyperliquidExecutor(testnet=True)
state = get_current_account_state(executor=executor, account=None, current_prices={}, is_live=True)

print(f"Balance: ${state['balance']:.2f}")
print(f"Equity: ${state['equity']:.2f}")
print(f"Positions: {state['num_positions']}")

print("\n=== Updating Database ===")
save_account_state(
    balance_usd=state['balance'],
    equity_usd=state['equity'],
    unrealized_pnl=state['unrealized_pnl'],
    realized_pnl=state['realized_pnl'],
    sharpe_ratio=None,
    num_positions=state['num_positions']
)

print("\n✓ Database updated!")
print("Dashboard should now show correct balance")
