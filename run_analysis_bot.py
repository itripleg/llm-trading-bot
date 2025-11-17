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
from datetime import datetime, timedelta
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from data.fetcher import MarketDataFetcher
from data.indicators import TechnicalIndicators
from llm.client import ClaudeClient
from llm.prompts import get_system_prompt, build_user_prompt
from llm.parser import parse_llm_response
from trading.logger import TradingLogger
from trading.account import TradingAccount
from trading.executor import HyperliquidExecutor  # Live trading
from config.settings import settings
from web.database import get_closed_positions, get_recent_decisions, set_database_path, save_account_state

# Control file for start/stop
CONTROL_FILE = Path(__file__).parent / "data" / "bot_control.txt"
RUNNING = False


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

            # Get positions from Hyperliquid
            positions_list = []
            for asset_pos in hl_state.get('positions', []):
                pos = asset_pos.get('position', {})
                coin = pos.get('coin', '')
                size = float(pos.get('szi', 0))

                if abs(size) > 0:  # Has open position
                    positions_list.append({
                        'coin': f"{coin}/USDC:USDC",
                        'side': 'long' if size > 0 else 'short',
                        'entry_price': float(pos.get('entryPx', 0)),
                        'current_price': float(pos.get('entryPx', 0)),  # TODO: Get live price
                        'quantity_usd': float(pos.get('marginUsed', 0)),
                        'leverage': pos.get('leverage', {}).get('value', 1),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0))
                    })

            return {
                'balance': hl_state.get('account_value', 0),
                'equity': hl_state.get('account_value', 0),
                'unrealized_pnl': hl_state.get('total_ntl_pos', 0),
                'realized_pnl': 0,  # Hyperliquid doesn't track this separately
                'total_pnl': hl_state.get('total_ntl_pos', 0),
                'num_positions': len(positions_list),
                'positions': positions_list
            }
        except Exception as e:
            print(f"[ERROR] Failed to get live account state: {e}", flush=True)
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

            result = executor.market_open_usd(
                coin=coin,
                is_buy=is_buy,
                usd_amount=decision.quantity_usd,
                current_price=current_price,
                leverage=int(decision.leverage),
                slippage=0.05  # 5% slippage tolerance
            )

            if result:
                print(f"  [SUCCESS] Live order executed!", flush=True)
            else:
                print(f"  [FAILED] Live order failed - check logs", flush=True)

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
            else:
                # Error details already printed by can_open_position()
                pass

    elif signal == 'close':
        if is_live:
            # LIVE TRADING - Close position
            print(f"  [LIVE] Closing {coin} position", flush=True)
            result = executor.market_close(coin)
            if result:
                print(f"  [SUCCESS] Position closed!", flush=True)
            else:
                print(f"  [INFO] No position to close or close failed", flush=True)
        else:
            # PAPER TRADING
            if coin in account.positions:
                account.close_position(coin, exit_price=current_price)
                print(f"  [PAPER] Position closed", flush=True)
            else:
                print(f"  [INFO] No position to close for {coin}", flush=True)

    elif signal == 'hold':
        # Just hold - same for both modes
        print(f"  [HOLD] No action taken", flush=True)
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
        print(f"ANALYSIS CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("="*70, flush=True)

        # Initialize
        fetcher = MarketDataFetcher()
        client = ClaudeClient()
        logger = TradingLogger()

        # Get assets from settings
        assets = [a.strip() for a in settings.trading_assets.split(',')]
        print(f"\n[1/4] Analyzing assets: {', '.join(assets)}", flush=True)

        # For now, just analyze the first asset (BTC)
        # TODO: Analyze all assets in future
        coin = assets[0]
        print(f"  Focusing on: {coin}", flush=True)

        # Fetch market data
        print(f"\n[2/4] Fetching market data for {coin}...", flush=True)
        ohlcv = fetcher.fetch_ohlcv(coin, timeframe='3m', limit=100)

        if ohlcv.empty:
            print(f"  [FAIL] Could not fetch data for {coin}", flush=True)
            return False

        current_price = ohlcv['close'].iloc[-1]
        print(f"  [OK] Current price: ${current_price:,.2f}", flush=True)

        # Calculate indicators
        print(f"\n[3/4] Calculating indicators...", flush=True)
        data_with_indicators = TechnicalIndicators.calculate_all(ohlcv)

        latest = data_with_indicators.iloc[-1]

        # Display market data summary
        print(f"\n" + "="*70, flush=True)
        print(f"MARKET DATA SUMMARY - {coin}", flush=True)
        print("="*70, flush=True)
        print(f"Current Price:    ${current_price:,.2f}", flush=True)
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
        if len(data_with_indicators) >= 2:
            prev_price = data_with_indicators['close'].iloc[-2]
            price_change = current_price - prev_price
            price_change_pct = (price_change / prev_price) * 100
            trend_symbol = "UP" if price_change > 0 else "DOWN" if price_change < 0 else "FLAT"
            print(f"", flush=True)
            print(f"Recent Movement:  {trend_symbol} ${price_change:+.2f} ({price_change_pct:+.2f}%)", flush=True)

        print("="*70, flush=True)

        # Get current account state (live or paper)
        current_prices = {coin: current_price}
        is_live = settings.is_live_trading() and executor is not None

        account_summary = get_current_account_state(
            executor=executor,
            account=account,
            current_prices=current_prices,
            is_live=is_live
        )

        print(f"\n[ACCOUNT] {'LIVE' if is_live else 'PAPER'} - " +
              f"Balance: ${account_summary['balance']:.2f}, " +
              f"Equity: ${account_summary['equity']:.2f}, " +
              f"Positions: {account_summary['num_positions']}", flush=True)

        # Build prompt with real account state
        market_data = {
            coin: {
                'current_price': current_price,
                'ohlcv': data_with_indicators,
                'indicators': data_with_indicators,
                'funding_rate': 0.0001,
                'open_interest': None,
            }
        }

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
        }

        # Calculate minutes since bot started
        minutes_since_start = int((datetime.now() - start_time).total_seconds() / 60)

        system_prompt = get_system_prompt()
        user_prompt = build_user_prompt(market_data, account_state, minutes_since_start)

        # Get Claude's decision
        print(f"\n[4/4] Getting Claude's analysis...", flush=True)
        print(f"  (This may take 10-30 seconds...)", flush=True)

        response = client.get_trading_decision(system_prompt, user_prompt)

        if not response:
            print("  [FAIL] No response from Claude", flush=True)
            return False

        # Parse decision
        decision = parse_llm_response(response)

        if not decision:
            print("  [FAIL] Could not parse response", flush=True)
            return False

        # For hold decisions, populate with current position details if available
        if decision.signal.value == 'hold' and coin in account.positions:
            position = account.positions[coin]
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
            coin=coin,
            current_price=current_price,
            decision_id=decision_id,
            account=account if not is_live else None,
            executor=executor if is_live else None,
            is_live=is_live
        )

        # Save updated account state to database (for dashboard)
        if not is_live:
            # Paper mode: use TradingAccount's save_state
            account.save_state(current_prices)
        else:
            # Live mode: save real Hyperliquid state to database
            save_account_state(
                balance_usd=account_summary['balance'],
                equity_usd=account_summary['equity'],
                unrealized_pnl=account_summary['unrealized_pnl'],
                realized_pnl=account_summary['realized_pnl'],
                sharpe_ratio=None,
                num_positions=account_summary['num_positions']
            )

        logger.log_bot_status('running', f'Executed {decision.signal.value} for {coin}')

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

    print("="*70, flush=True)
    mode = "LIVE TRADING" if settings.is_live_trading() else "PAPER TRADING"
    print(f"ALPHA ARENA MINI - {mode} BOT", flush=True)
    print("="*70, flush=True)

    if settings.is_live_trading():
        print("\n[!!!] LIVE TRADING MODE - REAL MONEY AT RISK [!!!]", flush=True)
        print(f"Testnet: {settings.hyperliquid_testnet}", flush=True)
    else:
        print("\nThis bot trades with simulated money (paper trading).", flush=True)
        print("Claude makes decisions, bot executes them with fake balance.", flush=True)

    print("\nControls:", flush=True)
    print("  - Dashboard: http://localhost:5000", flush=True)
    print("  - Ctrl+C: Stop the bot", flush=True)
    print("  - Control file:", CONTROL_FILE, flush=True)
    print("\n" + "="*70, flush=True)

    # Set database path based on mode (separate DBs for paper vs live)
    db_mode = "live" if settings.is_live_trading() else "paper"
    set_database_path(db_mode)
    print(f"\nUsing database: trading_bot_{db_mode}.db", flush=True)

    # Initialize components based on mode
    executor = None
    account = None

    if settings.is_live_trading():
        # LIVE MODE: Initialize Hyperliquid executor
        print("\nInitializing Hyperliquid executor...", flush=True)
        try:
            executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)

            # Get and display real account balance
            live_state = executor.get_account_state()
            balance = live_state.get('account_value', 0)
            print(f"Executor initialized successfully!", flush=True)
            print(f"Live account balance: ${balance:.2f}", flush=True)

            # Create dummy TradingAccount for internal use (not used for balance tracking)
            account = TradingAccount(initial_balance=1000.0)
        except Exception as e:
            print(f"[ERROR] Failed to initialize executor: {e}", flush=True)
            print("Make sure HYPERLIQUID_WALLET_PRIVATE_KEY is set in .env", flush=True)
            return
        print("="*70, flush=True)
    else:
        # PAPER MODE: Initialize simulated trading account
        print("\nInitializing paper trading account...", flush=True)
        account = TradingAccount(initial_balance=1000.0)
        print(f"Account state: {account}", flush=True)
        print("="*70, flush=True)

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Mark as running
    write_control_state("running")
    RUNNING = True

    # Track bot start time
    start_time = datetime.now()
    print(f"Bot started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

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

            # Wait 2-3 minutes before next cycle
            wait_time = 150  # 2.5 minutes
            next_cycle_time = datetime.now() + timedelta(seconds=wait_time)
            print(f"\n[*] Waiting {wait_time} seconds until next cycle...", flush=True)
            print(f"    Next cycle at: {next_cycle_time.strftime('%H:%M:%S')}", flush=True)
            print(f"    Press Ctrl+C to stop", flush=True)

            # Sleep in small chunks so we can respond to stop quickly
            # Show countdown every 30 seconds
            for i in range(wait_time):
                try:
                    # Check control state with error handling
                    state = read_control_state()
                    if state != "running":
                        print(f"[!] Bot state changed to: {state}", flush=True)
                        break

                    # Show progress every 30 seconds
                    if i > 0 and i % 30 == 0:
                        remaining = wait_time - i
                        print(f"    [{remaining}s remaining...]", flush=True)

                    time.sleep(1)
                except Exception as e:
                    # Log any errors but continue waiting
                    print(f"[WARNING] Error during wait: {e}", flush=True)
                    time.sleep(1)
                    continue

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
