"""Sync current Hyperliquid positions to database"""
from trading.executor import HyperliquidExecutor
from config.settings import settings
from web.database import set_database_path
from trading.logger import TradingLogger
from run_analysis_bot import get_current_account_state
from datetime import datetime

# Set correct database based on trading mode
db_mode = "live" if settings.is_live_trading() else "paper"
set_database_path(db_mode)
print(f"Using database: trading_bot_{db_mode}.db\n")

executor = HyperliquidExecutor(testnet=True)
logger = TradingLogger()

print("=== Querying Hyperliquid Positions ===")
state = get_current_account_state(executor=executor, account=None, current_prices={}, is_live=True)
positions = state.get('positions', [])

print(f"Found {len(positions)} positions on Hyperliquid\n")

for pos in positions:
    coin = pos['coin']
    side = pos['side']
    entry_price = pos['entry_price']
    quantity_usd = pos['quantity_usd']
    leverage = pos['leverage']

    position_id = f"{coin.split('/')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"Syncing: {coin} {side.upper()} @ ${entry_price:.2f}")
    print(f"  Size: ${quantity_usd:.2f}, Leverage: {leverage}x")
    print(f"  Position ID: {position_id}")

    logger.log_position_entry(
        position_id=position_id,
        coin=coin,
        side=side,
        entry_price=entry_price,
        quantity_usd=quantity_usd,
        leverage=leverage
    )
    print(f"  [OK] Saved to database\n")

print("=== Sync Complete ===")
print(f"Total positions synced: {len(positions)}")
print("\nPositions should now be visible on the dashboard!")
