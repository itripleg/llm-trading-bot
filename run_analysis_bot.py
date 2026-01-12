#!/usr/bin/env python3
"""
Continuous analysis bot that fetches market data and gets Claude decisions.

Runs every 2-3 minutes to collect real trading decisions from Claude.
No actual trading - just analysis and data collection.

Control via:
- Web dashboard (http://localhost:5000)
- This script: python run_analysis_bot.py [start|stop|status]
"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Backport for older Python versions if needed, though 3.9+ has it
    from backports.zoneinfo import ZoneInfo

from typing import Dict, Any
import msvcrt  # Windows-specific key detection

# Define Eastern Timezone
EST_TIMEZONE = ZoneInfo("America/New_York")

def flush_input():
    """Flush pending input from the buffer to prevent ghost commands."""
    while msvcrt.kbhit():
        msvcrt.getch()

sys.path.insert(0, str(Path(__file__).parent))

from data.fetcher import MarketDataFetcher
from data.indicators import TechnicalIndicators
from llm.client import ClaudeClient
from llm.prompts import PromptBuilder, TradingConfig
from llm.parser import parse_llm_response
from trading.logger import TradingLogger
from trading.account import TradingAccount
from trading.executor import HyperliquidExecutor  # Live trading
from config.settings import settings
from web.database import (
    get_closed_positions,
    get_recent_decisions,
    set_database_path,
    save_account_state,
    update_decision_execution,
    save_position_entry,
    close_position,
    get_open_positions,
    get_active_user_input,
    get_active_prompt_preset,
    get_bot_config
)

# Control file for start/stop
CONTROL_FILE = Path(__file__).parent / "data" / "bot_control.txt"
RUNNING = False

# Global context for interactive queries
LATEST_CONTEXT = {
    'executor': None,
    'account': None,
    'is_live': False
}

def print_live_status():
    """Fetch and display current status of active positions."""
    print("\n" + "="*70)
    print("\n" + "="*70)
    print(f"LIVE STATUS CHECK - {datetime.now(EST_TIMEZONE).strftime('%H:%M:%S')} ET")
    print("="*70)
    
    executor = LATEST_CONTEXT.get('executor')
    account = LATEST_CONTEXT.get('account')
    is_live = LATEST_CONTEXT.get('is_live', False)
    
    if is_live and executor:
        try:
            # Re-use get_current_account_state which fetches live prices/positions
            from data.fetcher import MarketDataFetcher
            
            # We need current prices for the summary calculation
            # But get_current_account_state does a decent job for live mode 
            # by querying the exchange directly
            state = get_current_account_state(executor=executor, is_live=True)
            
            print(f"Balance: ${state['balance']:.2f}")
            print(f"Equity:  ${state['equity']:.2f}")
            print(f"PnL:     ${state['unrealized_pnl']:+.2f}")
            
            if state['positions']:
                print("\nActive Positions:")
                for pos in state['positions']:
                    # Try to fetch fresh price if possible, otherwise use what we got
                    print(f"  {pos['coin']:<15} {pos['side'].upper():<5} "
                          f"${pos['quantity_usd']:>7.2f} "
                          f"PnL: ${pos['unrealized_pnl']:>+7.2f}")
            else:
                print("\nNo active positions.")
                
        except Exception as e:
            print(f"Error fetching live status: {e}")
            
    elif not is_live and account:
        # Paper trading
        print("PAPER TRADING MODE")
        # For paper, we need to fetch current prices to show accurate PnL and check liquidations
        fetcher = MarketDataFetcher()
        current_prices = {}
        
        if account.positions:
            print("\nFetching current prices & checking liquidations...")
            for coin in account.positions:
                try:
                    df = fetcher.fetch_ohlcv(coin, limit=1)
                    if not df.empty:
                        current_prices[coin] = df['close'].iloc[-1]
                except:
                    pass
            
            # Check for liquidations
            liquidated_ids = account.check_liquidation(current_prices)
            if liquidated_ids:
                print(f"[ALERT] {len(liquidated_ids)} positions liquidated during status check!")
        
        summary = account.get_summary(current_prices)
        print(f"Balance: ${summary['balance']:.2f}")
        print(f"Equity:  ${summary['equity']:.2f}")
        print(f"PnL:     ${summary['unrealized_pnl']:+.2f}")
        
        if summary['positions']:
            print("\nActive Positions:")
            for pos in summary['positions']:
                print(f"  {pos['coin']:<15} {pos['side'].upper():<5} "
                      f"${pos['quantity_usd']:>7.2f} "
                      f"PnL: ${pos['unrealized_pnl']:>+7.2f}")
        else:
            print("\nNo active positions.")
    else:
        print("Bot context not fully initialized yet.")
    
    print("="*70)
    print("Resume waiting...", end="", flush=True)


def read_control_state():
    """Read the bot control state from file."""
    if not CONTROL_FILE.exists():
        return "stopped"

    try:
        return CONTROL_FILE.read_text().strip()
    except:
        return "stopped"


def write_control_state(state):
    """Write the bot control state to file."""
    CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTROL_FILE.write_text(state)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n[!] Stopping bot...", flush=True)
    write_control_state("stopped")
    sys.exit(0)


def get_current_account_state(
    executor: HyperliquidExecutor = None,
    account: TradingAccount = None,
    current_prices: Dict[str, float] = None,
    is_live: bool = False
) -> Dict[str, Any]:
    """
    Get current account state from either live exchange or paper trading account.

    Args:
        executor: HyperliquidExecutor for live mode
        account: TradingAccount for paper mode
        current_prices: Current market prices (for paper mode unrealized PnL)
        is_live: True for live mode, False for paper mode

    Returns:
        Dict with unified account state format
    """
    if is_live and executor:
        # LIVE MODE: Query real account state from Hyperliquid
        try:
            hl_state = executor.get_account_state()

            # Check if we got valid data
            if not hl_state:
                print("[WARNING] Hyperliquid returned empty state", flush=True)
                print("  This may indicate:", flush=True)
                print("    - API connection issues", flush=True)
                print("    - Geographic restrictions (Hyperliquid blocks some regions)", flush=True)
                print("    - Network connectivity problems", flush=True)
                print("  You should still be able to query, but trading may be restricted", flush=True)
                # Return empty state
                return {
                    'balance': 0,
                    'equity': 0,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'total_pnl': 0,
                    'num_positions': 0,
                    'positions': []
                }

            # Get positions from Hyperliquid
            positions_list = []
            total_unrealized_pnl = 0.0

            for asset_pos in hl_state.get('positions', []):
                pos = asset_pos.get('position', {})
                coin = pos.get('coin', '')
                size = float(pos.get('szi', 0))

                if abs(size) > 0:  # Has open position
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                    total_unrealized_pnl += unrealized_pnl

                    # NOTE: Hyperliquid doesn't provide entry_time, so we use a placeholder
                    # For accurate tracking, positions should be logged to DB when opened
                    
                    # Hyperliquid returns short symbols like "ARB", "BTC", "ETH"
                    # We use simple symbols throughout the app now
                    full_symbol = coin
                    
                    positions_list.append({
                        'coin': full_symbol,
                        'side': 'long' if size > 0 else 'short',
                        'entry_price': float(pos.get('entryPx', 0)),
                        'current_price': float(pos.get('entryPx', 0)),  # TODO: Get live price
                        'quantity_usd': float(pos.get('marginUsed', 0)),
                        'leverage': pos.get('leverage', {}).get('value', 1),
                        'unrealized_pnl': unrealized_pnl,
                        'entry_time': None  # Hyperliquid doesn't track this - use DB instead
                    })

            # Calculate balance and equity
            # account_value from Hyperliquid = withdrawable amount = balance + unrealized PnL
            account_value = float(hl_state.get('account_value', 0))
            balance = account_value - total_unrealized_pnl  # Actual balance without PnL
            equity = account_value  # Total account value including unrealized PnL

            return {
                'balance': balance,
                'equity': equity,
                'unrealized_pnl': total_unrealized_pnl,  # Sum of all position PnLs
                'realized_pnl': 0,  # Hyperliquid doesn't track this separately
                'total_pnl': total_unrealized_pnl,  # Only unrealized for now
                'num_positions': len(positions_list),
                'positions': positions_list
            }
        except Exception as e:
            print(f"\n[ERROR] Failed to get live account state from Hyperliquid", flush=True)
            print(f"  Error details: {e}", flush=True)
            print(f"\n  Possible causes:", flush=True)
            print(f"    1. Geographic restrictions - Hyperliquid blocks certain regions", flush=True)
            print(f"       If you're in a blocked region, you cannot query OR trade", flush=True)
            print(f"       Solution: Use a VPN or move to a supported region", flush=True)
            print(f"    2. Network connectivity issues", flush=True)
            print(f"       Solution: Check your internet connection", flush=True)
            print(f"    3. Invalid API credentials", flush=True)
            print(f"       Solution: Check HYPERLIQUID_WALLET_PRIVATE_KEY in .env", flush=True)
            print(f"    4. Hyperliquid API downtime", flush=True)
            print(f"       Solution: Check https://status.hyperliquid.xyz/", flush=True)
            import traceback
            traceback.print_exc()
            # Return empty state on error
            return {
                'balance': 0,
                'equity': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'total_pnl': 0,
                'num_positions': 0,
                'positions': []
            }
    else:
        # PAPER MODE: Use TradingAccount
        return account.get_summary(current_prices or {})


def execute_trade(
    decision,
    coin: str,
    current_price: float,
    decision_id: int,
    account: TradingAccount = None,
    executor: HyperliquidExecutor = None,
    is_live: bool = False
):
    """
    Execute a trading decision in paper or live mode.

    Args:
        decision: TradeDecision object from Claude
        coin: Coin symbol (e.g., "BTC/USDC:USDC")
        current_price: Current market price
        decision_id: ID of decision being executed
        account: TradingAccount for paper trading (required if not live)
        executor: HyperliquidExecutor for live trading (required if live)
        is_live: True for live trading, False for paper trading
    """
    signal = decision.signal.value

    print(f"\n[EXECUTION] {'LIVE' if is_live else 'PAPER'} MODE: {signal.upper()}", flush=True)

    if signal == 'buy_to_enter' or signal == 'sell_to_enter':
        is_buy = (signal == 'buy_to_enter')

        if is_live:
            # LIVE TRADING
            print(f"  [LIVE] Opening {'LONG' if is_buy else 'SHORT'} position", flush=True)
            print(f"    Coin: {coin}", flush=True)
            print(f"    Margin: ${decision.quantity_usd:.2f}", flush=True)
            print(f"    Leverage: {decision.leverage}x", flush=True)
            print(f"    Price: ${current_price:,.2f}", flush=True)

            # Cap leverage for live trading (safety check)
            # Hyperliquid max is typically 20x or 50x depending on coin, but definitely not 100x for most
            safe_leverage = min(int(decision.leverage), 20)
            if safe_leverage < int(decision.leverage):
                print(f"    [WARN] Capping leverage from {decision.leverage}x to {safe_leverage}x for live safety", flush=True)

            result = executor.market_open_usd(
                coin=coin,
                is_buy=is_buy,
                usd_amount=decision.quantity_usd,
                current_price=current_price,
                leverage=safe_leverage,
                slippage=0.05  # 5% slippage tolerance
            )

            if result and result.get("status") == "ok":
                # Check if order was actually filled
                filled = False
                error_msg = None
                fill_price = None
                fill_size = None

                for status in result.get("response", {}).get("data", {}).get("statuses", []):
                    if "filled" in status:
                        filled_info = status["filled"]
                        fill_price = float(filled_info.get('avgPx', current_price))
                        fill_size = float(filled_info.get('totalSz', 0))
                        print(f"  [SUCCESS] Order filled: {fill_size} @ ${fill_price}", flush=True)
                        filled = True
                    elif "error" in status:
                        error_msg = status["error"]
                        print(f"  [FAILED] Order rejected: {error_msg}", flush=True)

                # Log filled position to database
                if filled and fill_price:
                    from datetime import datetime
                    from trading.logger import get_logger
                    trade_logger = get_logger()
                    position_id = f"{coin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    trade_logger.log_position_entry(
                        position_id=position_id,
                        coin=coin,
                        side='long' if is_buy else 'short',
                        entry_price=fill_price,
                        quantity_usd=decision.quantity_usd,
                        leverage=decision.leverage
                    )
                    print(f"  [DB] Position logged: {position_id}", flush=True)
                    # Update decision execution status to success
                    update_decision_execution(decision_id, 'success')
                elif error_msg:
                    # Update decision execution status with error
                    update_decision_execution(decision_id, 'failed', error=error_msg)
                    # Also log to bot_status for visibility
                    from trading.logger import get_logger
                    get_logger().log_bot_status('error', f'Trade execution failed for {coin}', error=error_msg)

                if not filled and not error_msg:
                    print(f"  [UNKNOWN] Order status unclear - check Hyperliquid", flush=True)
                    update_decision_execution(decision_id, 'failed', error='Order status unclear from Hyperliquid')
            else:
                print(f"  [FAILED] Live order failed - check logs", flush=True)
                error_detail = result.get('error', 'Unknown API error') if result else 'No response from Hyperliquid'
                update_decision_execution(decision_id, 'failed', error=error_detail)

        else:
            # PAPER TRADING
            side = 'long' if is_buy else 'short'
            if account.can_open_position(decision.quantity_usd, decision.leverage):
                account.open_position(
                    coin=coin,
                    side=side,
                    entry_price=current_price,
                    quantity_usd=decision.quantity_usd,
                    leverage=decision.leverage,
                    decision_id=decision_id
                )
                print(f"  [PAPER] Opened {side} position", flush=True)
                update_decision_execution(decision_id, 'success')
            else:
                # Error details already printed by can_open_position()
                update_decision_execution(decision_id, 'skipped', error='Insufficient balance or risk limits exceeded')

    elif signal == 'close':
        if is_live:
            # LIVE TRADING - Close position
            print(f"  [LIVE] Closing {coin} position", flush=True)
            result = executor.market_close(coin)
            if result:
                print(f"  [SUCCESS] Position closed!", flush=True)
                update_decision_execution(decision_id, 'success')
                
                # Log to database
                # First check if we have this position tracked in DB
                open_positions = get_open_positions()
                db_position = next((p for p in open_positions if p['coin'] == coin), None)
                
                if db_position:
                    # Calculate realized PnL
                    entry_price = db_position['entry_price']
                    quantity_usd = db_position['quantity_usd']
                    leverage = db_position['leverage']
                    side = db_position['side']

                    # Calculate actual quantity in coins (quantity_usd / entry_price)
                    quantity_coins = quantity_usd / entry_price

                    # Calculate PnL based on side
                    if side == 'long' or side == 'buy_to_enter':
                        # Long: profit when price goes up
                        price_change = current_price - entry_price
                        realized_pnl = (price_change / entry_price) * quantity_usd * leverage
                    elif side == 'short' or side == 'sell_to_enter':
                        # Short: profit when price goes down
                        price_change = entry_price - current_price
                        realized_pnl = (price_change / entry_price) * quantity_usd * leverage
                    else:
                        # Unknown side, can't calculate properly
                        realized_pnl = 0.0
                        print(f"  [WARNING] Unknown position side '{side}', cannot calculate PnL accurately", flush=True)

                    # Close existing DB position
                    close_position(
                        position_id=db_position['position_id'],
                        exit_price=current_price,
                        realized_pnl=realized_pnl
                    )
                    print(f"  [DB] Position closed: {db_position['position_id']} | Realized PnL: ${realized_pnl:.2f}", flush=True)
                else:
                    # Position was opened externally or before bot started
                    # Try to get position data from Hyperliquid to calculate real PnL
                    from datetime import datetime
                    position_id = f"{coin}_EXT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                    # Fetch position data from exchange
                    position_data = executor.get_position(coin)

                    if position_data:
                        entry_price = position_data['entry_price']
                        size = position_data['size']
                        unrealized_pnl = position_data['unrealized_pnl']
                        leverage_val = position_data.get('leverage', {}).get('value', decision.leverage)

                        # Determine side from size (positive = long, negative = short)
                        side = 'long' if size > 0 else 'short'

                        # Use the unrealized PnL from exchange as realized PnL since we're closing
                        realized_pnl = unrealized_pnl

                        # Calculate quantity in USD
                        quantity_usd = abs(size) * entry_price

                        print(f"  [INFO] Retrieved external position data: entry=${entry_price:.2f}, size={size:.4f}, unrealized_pnl=${unrealized_pnl:.2f}", flush=True)
                    else:
                        # Couldn't get position data, use placeholders
                        entry_price = current_price
                        side = 'unknown'
                        quantity_usd = decision.quantity_usd
                        leverage_val = decision.leverage
                        realized_pnl = 0.0
                        print(f"  [WARNING] Could not retrieve external position data, using placeholders", flush=True)

                    # Log the position entry
                    save_position_entry(
                        position_id=position_id,
                        coin=coin,
                        side=side,
                        entry_price=entry_price,
                        quantity_usd=quantity_usd,
                        leverage=leverage_val,
                        decision_id=decision_id
                    )

                    # Close the position with calculated PnL
                    close_position(
                        position_id=position_id,
                        exit_price=current_price,
                        realized_pnl=realized_pnl
                    )
                    print(f"  [DB] External position logged and closed: {position_id} | Realized PnL: ${realized_pnl:.2f}", flush=True)
            else:
                print(f"  [INFO] No position to close or close failed", flush=True)
                update_decision_execution(decision_id, 'failed', error='No position to close or close operation failed')
        else:
            # PAPER TRADING
            if coin in account.positions:
                account.close_position(coin, exit_price=current_price)
                print(f"  [PAPER] Position closed", flush=True)
                update_decision_execution(decision_id, 'success')
            else:
                print(f"  [INFO] No position to close for {coin}", flush=True)
                update_decision_execution(decision_id, 'skipped', error='No position to close')

    elif signal == 'hold':
        # Just hold - same for both modes
        print(f"  [HOLD] No action taken", flush=True)
        update_decision_execution(decision_id, 'success')  # Hold is always successful
        if not is_live and coin in account.positions:
            unrealized_pnl = account.positions[coin].calculate_pnl(current_price)
            print(f"    Current position unrealized PnL: ${unrealized_pnl:+.2f}", flush=True)
        elif is_live:
            position_info = executor.get_position_info(coin)
            if position_info:
                print(f"    Current position unrealized PnL: ${position_info['unrealized_pnl']:+.2f}", flush=True)


def run_analysis_cycle(account: TradingAccount, start_time: datetime, executor: HyperliquidExecutor = None):
    """
    Run one analysis cycle:
    1. Fetch market data for all configured assets
    2. Calculate indicators
    3. Get Claude's decision
    4. Execute decision (paper or live trading based on mode)
    5. Log to database

    Args:
        account: TradingAccount instance to track balance and positions
        start_time: Bot start time to calculate minutes since start
        executor: Optional HyperliquidExecutor for live trading

    Returns:
        bool: True if successful, False if error
    """
    try:
        print("\n" + "="*70, flush=True)
        print("\n" + "="*70, flush=True)
        print(f"ANALYSIS CYCLE - {datetime.now(EST_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')} ET", flush=True)
        print("="*70, flush=True)

        # Initialize
        fetcher = MarketDataFetcher()
        client = ClaudeClient()
        logger = TradingLogger()
        
        # Load configuration
        bot_config = get_bot_config()

        # Get current account state first to see what positions exist
        is_live = settings.is_live_trading() and executor is not None

        # Get preliminary account state (without prices, just to see positions)
        account_summary = get_current_account_state(
            executor=executor,
            account=account,
            current_prices={},
            is_live=is_live
        )

        # Update global context for interactive queries
        global LATEST_CONTEXT
        LATEST_CONTEXT['executor'] = executor
        LATEST_CONTEXT['account'] = account
        LATEST_CONTEXT['is_live'] = is_live

        # Get assets to actively analyze from settings
        # This respects ACTIVE_TRADING_ASSETS if set, otherwise uses all TRADING_ASSETS
        coins_to_analyze = list(settings.get_active_trading_assets())

        # Add any coins with open positions that aren't in the active list
        # (We always need to analyze coins we have positions in)
        for pos in account_summary.get('positions', []):
            pos_coin = pos['coin']
            if pos_coin not in coins_to_analyze:
                coins_to_analyze.append(pos_coin)
                print(f"[INFO] Found open {pos_coin} position - adding to analysis list", flush=True)

        print(f"\n[1/4] Analyzing assets: {', '.join(coins_to_analyze)}", flush=True)

        # Fetch market data for all relevant coins
        print(f"\n[2/4] Fetching market data...", flush=True)
        market_data = {}
        current_prices = {}

        for coin in coins_to_analyze:
            print(f"  Fetching {coin}...", flush=True)
            ohlcv = fetcher.fetch_ohlcv(coin, timeframe='3m', limit=100)

            if ohlcv.empty:
                print(f"    [WARN] Could not fetch data for {coin}", flush=True)
                continue

            current_price = ohlcv['close'].iloc[-1]
            current_prices[coin] = current_price
            print(f"    [OK] Current price: ${current_price:,.2f}", flush=True)

            # Calculate indicators
            data_with_indicators = TechnicalIndicators.calculate_all(ohlcv)

            market_data[coin] = {
                'current_price': current_price,
                'ohlcv': data_with_indicators,
                'indicators': data_with_indicators,
                'funding_rate': 0.0001,
                'open_interest': None,
            }

        if not market_data:
            print(f"  [FAIL] Could not fetch data for any assets", flush=True)
            return False

        # Display market data summary for primary asset
        print(f"\n[3/4] Market summary...", flush=True)
        primary_coin = coins_to_analyze[0]
        if primary_coin in market_data:
            latest = market_data[primary_coin]['indicators'].iloc[-1]
            current_price = market_data[primary_coin]['current_price']

            # Get latest candle timestamp and convert to aware EST
            # OHLCV timestamps from ccxt/pandas are typically naive UTC (or just naive)
            # We treat them as UTC and convert to EST
            latest_candle_time = market_data[primary_coin]['ohlcv']['timestamp'].iloc[-1]
            if latest_candle_time.tzinfo is None:
                latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)
            
            latest_candle_time_est = latest_candle_time.astimezone(EST_TIMEZONE)
            current_time_est = datetime.now(EST_TIMEZONE)
            
            candle_age_seconds = (current_time_est - latest_candle_time_est).total_seconds()

            # Check if cycle interval is less than candle timeframe
            candle_timeframe_seconds = 3 * 60  # 3 minutes
            cycle_interval = bot_config['execution_interval_seconds']

            print(f"\n" + "="*70, flush=True)
            print(f"MARKET DATA SUMMARY - {primary_coin}", flush=True)
            print("="*70, flush=True)
            print(f"Current Price:    ${current_price:,.2f}", flush=True)
            print(f"Latest Candle:    {latest_candle_time_est.strftime('%Y-%m-%d %H:%M:%S')} ET ({candle_age_seconds:.0f}s ago)", flush=True)

            # Warning if cycle is faster than candle timeframe
            if cycle_interval < candle_timeframe_seconds:
                print(f"", flush=True)
                print(f"⚠️  WARNING: Cycle interval ({cycle_interval}s) < Candle timeframe ({candle_timeframe_seconds}s)", flush=True)
                print(f"   Bot may see the SAME candle data on consecutive cycles!", flush=True)
                print(f"   Recommended: Set cycle interval >= 180s (3 minutes) in Settings", flush=True)

            print(f"", flush=True)
            print(f"Technical Indicators (3-minute timeframe):", flush=True)
            print(f"  EMA-20:         ${latest.get('ema_20', 0):,.2f}", flush=True)
            print(f"  EMA-50:         ${latest.get('ema_50', 0):,.2f}", flush=True)
            print(f"  RSI-7:          {latest.get('rsi_7', 0):.2f}", flush=True)
            print(f"  RSI-14:         {latest.get('rsi_14', 0):.2f}", flush=True)
            print(f"  MACD:           {latest.get('macd', 0):.2f}", flush=True)
            print(f"  MACD Signal:    {latest.get('macd_signal', 0):.2f}", flush=True)
            print(f"  MACD Histogram: {latest.get('macd_hist', 0):.2f}", flush=True)

            # Show price trend
            indicators_df = market_data[primary_coin]['indicators']
            if len(indicators_df) >= 2:
                prev_price = indicators_df['close'].iloc[-2]
                price_change = current_price - prev_price
                price_change_pct = (price_change / prev_price) * 100
                trend_symbol = "UP" if price_change > 0 else "DOWN" if price_change < 0 else "FLAT"
                print(f"", flush=True)
                print(f"Recent Movement:  {trend_symbol} ${price_change:+.2f} ({price_change_pct:+.2f}%)", flush=True)

            print("="*70, flush=True)

        # Refresh account state with current prices
        account_summary = get_current_account_state(
            executor=executor,
            account=account,
            current_prices=current_prices,
            is_live=is_live
        )
        
        # Check liquidations for paper trading
        if not is_live and account and current_prices:
             liquidations = account.check_liquidation(current_prices)
             if liquidations:
                 print(f"\n[LIQUIDATION] {len(liquidations)} positions liquidated!", flush=True)
                 # Refresh summary again after liquidations
                 account_summary = get_current_account_state(
                    executor=executor,
                    account=account,
                    current_prices=current_prices,
                    is_live=is_live
                )

        print(f"\n[ACCOUNT] {'LIVE' if is_live else 'PAPER'} - " +
              f"Balance: ${account_summary['balance']:.2f}, " +
              f"Equity: ${account_summary['equity']:.2f}, " +
              f"Unrealized PnL: ${account_summary['unrealized_pnl']:+.2f}, " +
              f"Positions: {account_summary['num_positions']}", flush=True)

        # Display open positions details
        if account_summary['num_positions'] > 0:
            print(f"\n  Open Positions:", flush=True)
            for pos in account_summary['positions']:
                print(f"    {pos['coin']} {pos['side'].upper()}: " +
                      f"${pos['quantity_usd']:.2f} @ {pos['leverage']}x leverage, " +
                      f"Entry: ${pos['entry_price']:,.2f}, " +
                      f"PnL: ${pos['unrealized_pnl']:+.2f}", flush=True)

        # Pre-flight check: Skip analysis if balance is too low to trade
        # Pre-flight check: Skip analysis if balance is too low to trade
        # bot_config already loaded at start of cycle
        min_balance_threshold = bot_config['min_balance_threshold']

        if account_summary['balance'] < min_balance_threshold and account_summary['num_positions'] == 0:
            print(f"\n[SKIP] Balance ${account_summary['balance']:.2f} below minimum ${min_balance_threshold:.2f}", flush=True)
            print(f"       Cannot open new positions - skipping Claude analysis to save tokens", flush=True)
            print(f"       Adjust min_balance_threshold in Settings tab or add more funds", flush=True)
            logger.log_bot_status('paused', f'Insufficient balance: ${account_summary["balance"]:.2f}')
            return True  # Cycle complete, just can't trade

        # Get trade history for context (last 10 closed positions)
        trade_history = get_closed_positions(limit=10)

        # Get recent decisions for context (last 5 decisions)
        recent_decisions = get_recent_decisions(limit=5)

        account_state = {
            'available_cash': account_summary['balance'],
            'total_value': account_summary['equity'],
            'total_return_pct': account_summary.get('total_return_pct', 0.0),
            'sharpe_ratio': 0.0,  # TODO: Calculate Sharpe ratio
            'positions': account_summary['positions'],
            'trade_history': trade_history,
            'recent_decisions': recent_decisions,
            'max_positions': bot_config['max_open_positions'],  # Allow multiple positions
        }

        # Calculate minutes since bot started
        minutes_since_start = int((datetime.now(EST_TIMEZONE) - start_time).total_seconds() / 60)

        # Get active prompt preset from database
        active_preset = get_active_prompt_preset()
        print(f"[STRATEGY] Using prompt preset: {active_preset}", flush=True)

        # Create PromptBuilder with configuration from database
        trading_config = TradingConfig(
            exchange_name=settings.exchange_name if hasattr(settings, 'exchange_name') else "Hyperliquid",
            min_position_size_usd=bot_config['min_margin_usd'],  # This is margin (collateral), not notional
            max_leverage=settings.max_leverage if hasattr(settings, 'max_leverage') else 10.0,
            preset_name=active_preset,
        )
        prompt_builder = PromptBuilder(config=trading_config)
        
        # Get active user guidance
        active_input = get_active_user_input()
        user_guidance = active_input['message'] if active_input else None
        if user_guidance:
            print(f"\n[GUIDANCE] Active Supervisor Input: \"{user_guidance}\"", flush=True)

        # Fetch leverage limits from Hyperliquid for each coin
        leverage_limits = {}
        if executor:  # Only fetch if we have a live executor
            for symbol in market_data.keys():
                try:
                    max_lev = executor.get_max_leverage(symbol)
                    leverage_limits[symbol] = max_lev
                except Exception as e:
                    print(f"  [WARN] Could not fetch max leverage for {symbol}: {e}", flush=True)
                    leverage_limits[symbol] = 20  # Safe default
        else:
            # For paper trading, allow up to 100x
             for symbol in market_data.keys():
                 leverage_limits[symbol] = 100

        system_prompt = prompt_builder.get_system_prompt()
        user_prompt = prompt_builder.build_trading_prompt(
            market_data,
            account_state,
            minutes_since_start,
            user_guidance=user_guidance,
            leverage_limits=leverage_limits if leverage_limits else None
        )

        # Get Claude's decision
        print(f"\n[4/4] Getting Claude's analysis...", flush=True)
        print(f"  (This may take 10-30 seconds...)", flush=True)

        response = client.get_trading_decision(system_prompt, user_prompt)

        if not response:
            print("  [FAIL] No response from Claude", flush=True)
            return False

        # Parse decision (with leverage validation)
        decision = parse_llm_response(response, leverage_limits=leverage_limits)

        if not decision:
            print("  [FAIL] Could not parse response", flush=True)
            return False

        # Get the coin Claude decided on and its current price
        decision_coin = decision.coin
        decision_price = current_prices.get(decision_coin)

        if not decision_price:
            print(f"  [ERROR] No market data for {decision_coin}", flush=True)
            return False

        # For hold decisions, populate with current position details if available
        if decision.signal.value == 'hold':
            # In live mode, get position from account_summary; in paper mode, from account object
            if is_live and account_summary['positions']:
                # Find the matching position from live Hyperliquid data
                live_position = next((p for p in account_summary['positions'] if p['coin'] == decision_coin), None)
                if live_position:
                    decision.quantity_usd = live_position['quantity_usd']
                    decision.leverage = live_position['leverage']
                    print(f"  [HOLD] Populated with current position: ${live_position['quantity_usd']:.2f} @ {live_position['leverage']}x", flush=True)
            elif not is_live and decision_coin in account.positions:
                # Paper trading mode
                position = account.positions[decision_coin]
                decision.quantity_usd = position.quantity_usd
                decision.leverage = position.leverage
                print(f"  [HOLD] Populated with current position: ${position.quantity_usd:.2f} @ {position.leverage}x", flush=True)

        # Log decision to database (save both the response AND the prompts sent to Claude)
        decision_id = logger.log_decision_from_trade_decision(
            decision,
            raw_response=response,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Execute decision (paper or live mode)
        is_live = settings.is_live_trading() and executor is not None

        execute_trade(
            decision=decision,
            coin=decision_coin,
            current_price=decision_price,
            decision_id=decision_id,
            account=account if not is_live else None,
            executor=executor if is_live else None,
            is_live=is_live
        )

        # Save updated account state to database (for dashboard) and Motherhaven
        if not is_live:
            # Paper mode: use TradingAccount's save_state
            account.save_state(current_prices)
        else:
            # Live mode: save real Hyperliquid state to database AND Motherhaven
            logger.log_account_state(
                balance=account_summary['balance'],
                equity=account_summary['equity'],
                unrealized_pnl=account_summary['unrealized_pnl'],
                realized_pnl=account_summary['realized_pnl'],
                sharpe_ratio=None,
                num_positions=account_summary['num_positions']
            )

        # Log bot status (without trades_today for now - will add to logger later)
        logger.log_bot_status('running', f'Executed {decision.signal.value} for {decision_coin}')

        # Display decision
        print("\n" + "-"*70, flush=True)
        print("CLAUDE'S DECISION:", flush=True)
        print("-"*70, flush=True)
        print(f"Signal: {decision.signal.value.upper()}", flush=True)
        print(f"Confidence: {decision.confidence:.0%}", flush=True)
        print(f"Quantity: ${decision.quantity_usd:.2f}", flush=True)
        print(f"Leverage: {decision.leverage}x", flush=True)

        if decision.exit_plan.profit_target:
            print(f"Target: ${decision.exit_plan.profit_target:,.2f}", flush=True)
        if decision.exit_plan.stop_loss:
            print(f"Stop: ${decision.exit_plan.stop_loss:,.2f}", flush=True)

        print(f"\nJustification: {decision.justification[:150]}...", flush=True)
        print("-"*70, flush=True)
        print("[OK] Decision logged to database", flush=True)

        return True

    except Exception as e:
        print(f"\n[ERROR] Analysis cycle failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return False


def run_bot():
    """Main bot loop - runs continuously until stopped."""
    global RUNNING
    global LATEST_CONTEXT

    print("="*70, flush=True)
    mode = "LIVE TRADING" if settings.is_live_trading() else "PAPER TRADING"
    print(f"MOTHERBOT - {mode} BOT", flush=True)
    print("="*70, flush=True)

    if settings.is_live_trading():
        print("\n[!!!] LIVE TRADING MODE - REAL MONEY AT RISK [!!!]", flush=True)
        print(f"Testnet: {settings.hyperliquid_testnet}", flush=True)
    else:
        print("\nThis bot trades with simulated money (paper trading).", flush=True)
        print("Claude makes decisions, bot executes them with fake balance.", flush=True)

    print("\nControls:", flush=True)
    print("  - Dashboard: http://localhost:5000", flush=True)
    print("  - [p]rice: Check live PnL", flush=True)
    print("  - [q]uit or Ctrl+C: Stop the bot", flush=True)
    
    # Set database path based on mode (separate DBs for paper vs live)
    db_mode = "live" if settings.is_live_trading() else "paper"
    set_database_path(db_mode)
    print(f"  - Database: trading_bot_{db_mode}.db", flush=True)
    print("="*70, flush=True)



    # Initialize components based on mode
    executor = None
    account = None

    if settings.is_live_trading():
        # LIVE MODE: Initialize Hyperliquid executor
        print("\nInitializing Hyperliquid executor...", flush=True)
        try:
            executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)
            
            # Use unifying wrapper to get state
            state = get_current_account_state(executor=executor, is_live=True)
            
            print(f"Executor initialized successfully!", flush=True)
            print(f"Balance: ${state['balance']:.2f}")
            print(f"Equity:  ${state['equity']:.2f}")
            
            if state['positions']:
                print("\nActive Positions:", flush=True)
                for pos in state['positions']:
                    print(f"  {pos['coin']:<15} {pos['side'].upper():<5} "
                          f"${pos['quantity_usd']:>7.2f} "
                          f"PnL: ${pos['unrealized_pnl']:>+7.2f}", flush=True)
            else:
                 print("No active positions.", flush=True)

            # Create dummy TradingAccount for internal use
            account = TradingAccount(initial_balance=1000.0)
            
            LATEST_CONTEXT['executor'] = executor
            LATEST_CONTEXT['account'] = account
            LATEST_CONTEXT['is_live'] = True
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize executor: {e}", flush=True)
            print("Make sure HYPERLIQUID_WALLET_PRIVATE_KEY is set in .env", flush=True)
            return
    else:
        # PAPER MODE: Initialize simulated trading account
        print("\nInitializing paper trading account...", flush=True)
        account = TradingAccount(initial_balance=1000.0)
        print(f"Balance: ${account.balance:.2f}", flush=True)
        
        # Initialize global context immediately
        # global LATEST_CONTEXT # Already declared above if in same function scope? No, needs to be valid python.

        LATEST_CONTEXT['executor'] = None 
        LATEST_CONTEXT['account'] = account
        LATEST_CONTEXT['is_live'] = False
        
    print("="*70, flush=True)

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Mark as running
    write_control_state("running")
    RUNNING = True

    # Track bot start time
    start_time = datetime.now(EST_TIMEZONE)
    print(f"Bot started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ET", flush=True)

    cycle_count = 0

    try:
        while True:
            # Check control state
            state = read_control_state()

            if state != "running":
                print(f"\n[!] Bot paused. Waiting for resume signal...", flush=True)
                write_control_state("paused")

                # Wait until resumed
                while read_control_state() == "paused":
                    time.sleep(5)

                print("[!] Bot resumed!", flush=True)
                continue

            # Run analysis cycle
            cycle_count += 1
            print(f"\n{'='*70}", flush=True)
            print(f"CYCLE #{cycle_count}", flush=True)

            success = run_analysis_cycle(account, start_time, executor)

            if success:
                print(f"\n[OK] Cycle #{cycle_count} complete", flush=True)
            else:
                print(f"\n[FAIL] Cycle #{cycle_count} had errors", flush=True)

            # Wait before next cycle (configurable from Settings tab)
            bot_config = get_bot_config()
            wait_time = bot_config['execution_interval_seconds']
            next_cycle_time = datetime.now(EST_TIMEZONE) + timedelta(seconds=wait_time)

            # Save next cycle time for web dashboard countdown
            from web.database import set_bot_setting
            set_bot_setting('next_cycle_time', next_cycle_time.isoformat())

            # Sleep with key check
            # Check every 0.1s
            check_interval = 0.1
            steps = int(wait_time / check_interval)

            # Flush any accidental keystrokes before waiting
            flush_input()

            print(f"\n[*] Waiting {wait_time} seconds until next cycle...", flush=True)
            print(f"    Next cycle at: {next_cycle_time.strftime('%H:%M:%S')}", flush=True)
            print(f"    Commands: [p]rice check, [q]uit", flush=True)

            for i in range(steps):
                # Check for keypress
                if msvcrt.kbhit():
                    key = msvcrt.getch().lower()
                    if key == b'p':
                        print_live_status()
                    elif key == b'q':
                        print("\n[USER] Quit command received", flush=True)
                        raise KeyboardInterrupt
                
                # Update countdown display every 30 seconds
                current_time = i * check_interval
                if i > 0 and int(current_time) % 30 == 0 and abs(current_time - round(current_time)) < 0.01:
                     remaining = wait_time - int(current_time)
                     print(f"    [{remaining}s remaining...]", flush=True)
                
                # Check control file every 1 second
                if i % 10 == 0:
                    try:
                        state = read_control_state()
                        if state != "running":
                            print(f"[!] Bot state changed to: {state}", flush=True)
                            break
                    except:
                        pass
                
                time.sleep(check_interval)
                
    except KeyboardInterrupt:
        print("\n\n[!] Bot stopped by user", flush=True)
    finally:
        write_control_state("stopped")
        print("\n[*] Bot stopped", flush=True)


def get_status():
    """Get current bot status."""
    state = read_control_state()

    print(f"Bot status: {state.upper()}", flush=True)
    print(f"Control file: {CONTROL_FILE}", flush=True)

    if CONTROL_FILE.exists():
        print(f"Last modified: {datetime.fromtimestamp(CONTROL_FILE.stat().st_mtime)}", flush=True)

    return state


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "start":
            if read_control_state() == "running":
                print("Bot is already running!", flush=True)
                sys.exit(1)

            print("Starting bot...", flush=True)
            run_bot()

        elif command == "stop":
            print("Stopping bot...", flush=True)
            write_control_state("stopped")
            print("Bot stopped", flush=True)

        elif command == "pause":
            print("Pausing bot...", flush=True)
            write_control_state("paused")
            print("Bot paused", flush=True)

        elif command == "resume":
            print("Resuming bot...", flush=True)
            write_control_state("running")
            print("Bot resumed", flush=True)

        elif command == "status":
            get_status()

        else:
            print("Usage: python run_analysis_bot.py [start|stop|pause|resume|status]", flush=True)
            sys.exit(1)
    else:
        # No arguments - just start the bot
        run_bot()


if __name__ == "__main__":
    main()
