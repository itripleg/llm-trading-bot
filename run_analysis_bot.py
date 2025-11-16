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
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from data.fetcher import MarketDataFetcher
from data.indicators import TechnicalIndicators
from llm.client import ClaudeClient
from llm.prompts import get_system_prompt, build_user_prompt
from llm.parser import parse_llm_response
from trading.logger import TradingLogger
from trading.account import TradingAccount
from config.settings import settings
from web.database import get_closed_positions, get_recent_decisions

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
    print("\n\n[!] Stopping bot...")
    write_control_state("stopped")
    sys.exit(0)


def run_analysis_cycle(account: TradingAccount, start_time: datetime):
    """
    Run one analysis cycle:
    1. Fetch market data for all configured assets
    2. Calculate indicators
    3. Get Claude's decision
    4. Execute decision (paper trading)
    5. Log to database

    Args:
        account: TradingAccount instance to track balance and positions
        start_time: Bot start time to calculate minutes since start

    Returns:
        bool: True if successful, False if error
    """
    try:
        print("\n" + "="*70)
        print(f"ANALYSIS CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # Initialize
        fetcher = MarketDataFetcher()
        client = ClaudeClient()
        logger = TradingLogger()

        # Get assets from settings
        assets = [a.strip() for a in settings.trading_assets.split(',')]
        print(f"\n[1/4] Analyzing assets: {', '.join(assets)}")

        # For now, just analyze the first asset (BTC)
        # TODO: Analyze all assets in future
        coin = assets[0]
        print(f"  Focusing on: {coin}")

        # Fetch market data
        print(f"\n[2/4] Fetching market data for {coin}...")
        ohlcv = fetcher.fetch_ohlcv(coin, timeframe='3m', limit=100)

        if ohlcv.empty:
            print(f"  [FAIL] Could not fetch data for {coin}")
            return False

        current_price = ohlcv['close'].iloc[-1]
        print(f"  [OK] Current price: ${current_price:,.2f}")

        # Calculate indicators
        print(f"\n[3/4] Calculating indicators...")
        data_with_indicators = TechnicalIndicators.calculate_all(ohlcv)

        latest = data_with_indicators.iloc[-1]
        print(f"  RSI-14: {latest.get('rsi_14', 0):.2f}")
        print(f"  MACD: {latest.get('macd', 0):.2f}")
        print(f"  EMA-20: ${latest.get('ema_20', 0):,.2f}")

        # Get current account state
        current_prices = {coin: current_price}
        account_summary = account.get_summary(current_prices)

        print(f"\n[ACCOUNT] Balance: ${account_summary['balance']:.2f}, " +
              f"Equity: ${account_summary['equity']:.2f}, " +
              f"Positions: {account_summary['num_positions']}")

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
            'available_cash': account.balance,
            'total_value': account_summary['equity'],
            'total_return_pct': account_summary['total_return_pct'],
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
        print(f"\n[4/4] Getting Claude's analysis...")
        print(f"  (This may take 10-30 seconds...)")

        response = client.get_trading_decision(system_prompt, user_prompt)

        if not response:
            print("  [FAIL] No response from Claude")
            return False

        # Parse decision
        decision = parse_llm_response(response)

        if not decision:
            print("  [FAIL] Could not parse response")
            return False

        # Log decision to database (capture decision_id for position tracking)
        # Save both the response AND the prompts sent to Claude
        decision_id = logger.log_decision_from_trade_decision(
            decision,
            raw_response=response,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Execute decision (paper trading)
        print(f"\n[EXECUTION] Executing decision: {decision.signal.value.upper()}")

        if decision.signal.value == 'buy_to_enter':
            # Open long position
            if account.can_open_position(decision.quantity_usd):
                account.open_position(
                    coin=coin,
                    side='long',
                    entry_price=current_price,
                    quantity_usd=decision.quantity_usd,
                    leverage=decision.leverage,
                    decision_id=decision_id
                )
            else:
                print(f"  [REJECTED] Insufficient balance")
                print(f"    Required: ${decision.quantity_usd:.2f}")
                print(f"    Available: ${account.balance:.2f}")

        elif decision.signal.value == 'sell_to_enter':
            # Open short position
            if account.can_open_position(decision.quantity_usd):
                account.open_position(
                    coin=coin,
                    side='short',
                    entry_price=current_price,
                    quantity_usd=decision.quantity_usd,
                    leverage=decision.leverage,
                    decision_id=decision_id
                )
            else:
                print(f"  [REJECTED] Insufficient balance")
                print(f"    Required: ${decision.quantity_usd:.2f}")
                print(f"    Available: ${account.balance:.2f}")

        elif decision.signal.value == 'close':
            # Close existing position
            if coin in account.positions:
                account.close_position(coin, exit_price=current_price)
            else:
                print(f"  [INFO] No position to close for {coin}")

        elif decision.signal.value == 'hold':
            # Just hold, update unrealized PnL
            print(f"  [HOLD] No action taken")
            if coin in account.positions:
                unrealized_pnl = account.positions[coin].calculate_pnl(current_price)
                print(f"    Current position unrealized PnL: ${unrealized_pnl:+.2f}")

        # Save updated account state
        account.save_state(current_prices)
        logger.log_bot_status('running', f'Executed {decision.signal.value} for {coin}')

        # Display decision
        print("\n" + "-"*70)
        print("CLAUDE'S DECISION:")
        print("-"*70)
        print(f"Signal: {decision.signal.value.upper()}")
        print(f"Confidence: {decision.confidence:.0%}")
        print(f"Quantity: ${decision.quantity_usd:.2f}")
        print(f"Leverage: {decision.leverage}x")

        if decision.exit_plan.profit_target:
            print(f"Target: ${decision.exit_plan.profit_target:,.2f}")
        if decision.exit_plan.stop_loss:
            print(f"Stop: ${decision.exit_plan.stop_loss:,.2f}")

        print(f"\nJustification: {decision.justification[:150]}...")
        print("-"*70)
        print("[OK] Decision logged to database")

        return True

    except Exception as e:
        print(f"\n[ERROR] Analysis cycle failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_bot():
    """Main bot loop - runs continuously until stopped."""
    global RUNNING

    print("="*70)
    print("ALPHA ARENA MINI - PAPER TRADING BOT")
    print("="*70)
    print("\nThis bot trades with simulated money (paper trading).")
    print("Claude makes decisions, bot executes them with fake balance.")
    print("\nControls:")
    print("  - Dashboard: http://localhost:5000")
    print("  - Ctrl+C: Stop the bot")
    print("  - Control file:", CONTROL_FILE)
    print("\n" + "="*70)

    # Initialize trading account (loads from DB or starts with $1000)
    print("\nInitializing trading account...")
    account = TradingAccount(initial_balance=1000.0)
    print(f"Account state: {account}")
    print("="*70)

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Mark as running
    write_control_state("running")
    RUNNING = True

    # Track bot start time
    start_time = datetime.now()
    print(f"Bot started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    cycle_count = 0

    try:
        while True:
            # Check control state
            state = read_control_state()

            if state != "running":
                print(f"\n[!] Bot paused. Waiting for resume signal...")
                write_control_state("paused")

                # Wait until resumed
                while read_control_state() == "paused":
                    time.sleep(5)

                print("[!] Bot resumed!")
                continue

            # Run analysis cycle
            cycle_count += 1
            print(f"\n{'='*70}")
            print(f"CYCLE #{cycle_count}")

            success = run_analysis_cycle(account, start_time)

            if success:
                print(f"\n[OK] Cycle #{cycle_count} complete")
            else:
                print(f"\n[FAIL] Cycle #{cycle_count} had errors")

            # Wait 2-3 minutes before next cycle
            wait_time = 150  # 2.5 minutes
            from datetime import timedelta
            next_cycle_time = datetime.now() + timedelta(seconds=wait_time)
            print(f"\n[*] Waiting {wait_time} seconds until next cycle...")
            print(f"    Next cycle at: {next_cycle_time.strftime('%H:%M:%S')}")
            print(f"    Press Ctrl+C to stop")

            # Sleep in small chunks so we can respond to stop quickly
            # Print countdown every 30 seconds
            for i in range(wait_time):
                if read_control_state() != "running":
                    break
                # Show countdown at 120s, 90s, 60s, 30s remaining
                if i in [30, 60, 90, 120] and i < wait_time:
                    remaining = wait_time - i
                    print(f"    [{remaining}s remaining until next cycle...]")
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n[!] Bot stopped by user")
    finally:
        write_control_state("stopped")
        print("\n[*] Bot stopped")


def get_status():
    """Get current bot status."""
    state = read_control_state()

    print(f"Bot status: {state.upper()}")
    print(f"Control file: {CONTROL_FILE}")

    if CONTROL_FILE.exists():
        print(f"Last modified: {datetime.fromtimestamp(CONTROL_FILE.stat().st_mtime)}")

    return state


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "start":
            if read_control_state() == "running":
                print("Bot is already running!")
                sys.exit(1)

            print("Starting bot...")
            run_bot()

        elif command == "stop":
            print("Stopping bot...")
            write_control_state("stopped")
            print("Bot stopped")

        elif command == "pause":
            print("Pausing bot...")
            write_control_state("paused")
            print("Bot paused")

        elif command == "resume":
            print("Resuming bot...")
            write_control_state("running")
            print("Bot resumed")

        elif command == "status":
            get_status()

        else:
            print("Usage: python run_analysis_bot.py [start|stop|pause|resume|status]")
            sys.exit(1)
    else:
        # No arguments - just start the bot
        run_bot()


if __name__ == "__main__":
    main()
