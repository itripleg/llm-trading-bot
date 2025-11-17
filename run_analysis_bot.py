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

sys.path.insert(0, str(Path(__file__).parent))

from data.fetcher import MarketDataFetcher
from data.indicators import TechnicalIndicators
from llm.client import ClaudeClient
from llm.prompts import get_system_prompt, build_user_prompt
from llm.parser import parse_llm_response
from trading.logger import TradingLogger
from trading.account import TradingAccount
from trading.risk import RiskManager
from config.settings import settings
from web.database import get_closed_positions, get_recent_decisions, init_database

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

        # Display risk summary
        print(f"\n[RISK STATUS]", flush=True)
        risk_manager = RiskManager(account)
        risk_summary = risk_manager.get_risk_summary({coin: current_price})
        print(f"  Balance: ${risk_summary['available_balance']:.2f}", flush=True)
        print(f"  Daily P&L: ${risk_summary['daily_pnl']:+.2f} / Limit: ${risk_summary['daily_loss_limit']:.2f}", flush=True)
        if risk_summary['trading_halted']:
            print(f"  ⚠️  TRADING HALTED - Daily loss limit exceeded!", flush=True)
        if risk_summary['positions_at_risk'] > 0:
            print(f"  ⚠️  {risk_summary['positions_at_risk']} position(s) approaching liquidation!", flush=True)
        print(f"  Open Positions: {risk_summary['num_positions']}", flush=True)

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

        # Get current account state
        current_prices = {coin: current_price}
        account_summary = account.get_summary(current_prices)

        print(f"\n[ACCOUNT] Balance: ${account_summary['balance']:.2f}, " +
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

        # Calculate Sharpe ratio from trade history
        sharpe_ratio = account.calculate_sharpe_ratio()

        account_state = {
            'available_cash': account.balance,
            'total_value': account_summary['equity'],
            'total_return_pct': account_summary['total_return_pct'],
            'sharpe_ratio': sharpe_ratio if sharpe_ratio is not None else 0.0,
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

        # === RISK VALIDATION ===
        # Validate trade against all safety limits BEFORE execution
        risk_manager = RiskManager(account)
        is_valid, rejection_reason = risk_manager.validate_trade(decision, current_price)

        if not is_valid:
            print(f"\n[RISK CHECK] ❌ TRADE REJECTED", flush=True)
            print(f"  Reason: {rejection_reason}", flush=True)
            print(f"  Decision: {decision.signal.value.upper()} {coin} ${decision.quantity_usd:.2f} @ {decision.leverage}x", flush=True)
            return True  # Continue bot loop (don't crash on rejection)

        # Trade passed risk validation
        print(f"[RISK CHECK] ✅ Trade validated", flush=True)

        # Execute decision (paper trading)
        print(f"\n[EXECUTION] Executing decision: {decision.signal.value.upper()}", flush=True)
        balance_before = account.balance
        print(f"  Balance before execution: ${balance_before:.2f}", flush=True)

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
                print(f"  Balance after opening position: ${account.balance:.2f}", flush=True)
                print(f"  Change: ${account.balance - balance_before:+.2f} (margin locked)", flush=True)
            else:
                print(f"  [REJECTED] Insufficient balance", flush=True)
                print(f"    Required: ${decision.quantity_usd:.2f}", flush=True)
                print(f"    Available: ${account.balance:.2f}", flush=True)

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
                print(f"  Balance after opening position: ${account.balance:.2f}", flush=True)
                print(f"  Change: ${account.balance - balance_before:+.2f} (margin locked)", flush=True)
            else:
                print(f"  [REJECTED] Insufficient balance", flush=True)
                print(f"    Required: ${decision.quantity_usd:.2f}", flush=True)
                print(f"    Available: ${account.balance:.2f}", flush=True)

        elif decision.signal.value == 'close':
            # Close existing position
            if coin in account.positions:
                account.close_position(coin, exit_price=current_price)
                print(f"  Balance after closing position: ${account.balance:.2f}", flush=True)
                print(f"  Change: ${account.balance - balance_before:+.2f} (margin returned + P&L)", flush=True)
            else:
                print(f"  [INFO] No position to close for {coin}", flush=True)

        elif decision.signal.value == 'hold':
            # Just hold, update unrealized PnL
            print(f"  [HOLD] No action taken", flush=True)
            if coin in account.positions:
                unrealized_pnl = account.positions[coin].calculate_pnl(current_price)
                print(f"    Current position unrealized PnL: ${unrealized_pnl:+.2f}", flush=True)

        # Save updated account state
        print(f"\n[DATABASE] Saving account state...", flush=True)
        print(f"  Balance to save: ${account.balance:.2f}", flush=True)
        print(f"  Realized P&L: ${account.realized_pnl:+.2f}", flush=True)
        print(f"  Open positions: {len(account.positions)}", flush=True)
        account.save_state(current_prices)
        print(f"  [OK] Account state saved to database", flush=True)
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
    print("ALPHA ARENA MINI - PAPER TRADING BOT", flush=True)
    print("="*70, flush=True)
    print("\nThis bot trades with simulated money (paper trading).", flush=True)
    print("Claude makes decisions, bot executes them with fake balance.", flush=True)
    print("\nControls:", flush=True)
    print("  - Dashboard: http://localhost:5000", flush=True)
    print("  - Ctrl+C: Stop the bot", flush=True)
    print("  - Control file:", CONTROL_FILE, flush=True)
    print("\n" + "="*70, flush=True)

    # Initialize database (must happen before TradingAccount creation)
    print("\nInitializing database...", flush=True)
    init_database()
    print("[OK] Database initialized at data/trading_bot.db", flush=True)

    # Initialize trading account (loads from DB or starts with $1000)
    print("\nInitializing trading account...", flush=True)
    print("  Attempting to load previous state from database...", flush=True)
    account = TradingAccount(initial_balance=1000.0)

    # Display account summary
    summary = account.get_summary({})
    print(f"\n[OK] Account ready:", flush=True)
    print(f"  💰 Balance: ${account.balance:.2f}", flush=True)
    print(f"  📊 Realized P&L: ${account.realized_pnl:+.2f}", flush=True)
    print(f"  📍 Open Positions: {len(account.positions)}", flush=True)
    if account.positions:
        for coin, pos in account.positions.items():
            print(f"    - {coin}: {pos.side} ${pos.quantity_usd:.2f} @ {pos.leverage}x", flush=True)
            print(f"      Entry: ${pos.entry_price:.2f} | Margin locked: ${pos.quantity_usd:.2f}", flush=True)
    else:
        print(f"    (No open positions - ready to trade)", flush=True)

    # Show what will happen with balance
    print(f"\n  ℹ️  Note: When position opens, margin is deducted from balance", flush=True)
    print(f"     When position closes, margin + P&L is returned to balance", flush=True)
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

            success = run_analysis_cycle(account, start_time)

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
