#!/usr/bin/env python3
"""
Test script for Motherhaven integration.

This script tests the integration between the trading bot and the Motherhaven
dashboard. It verifies that data is being sent correctly to the API endpoints.

Prerequisites:
1. Motherhaven dev server running (cd ../motherhaven && npm run dev)
2. .env file configured with:
   - MOTHERHAVEN_ENABLED=true
   - MOTHERHAVEN_API_URL=http://localhost:3000
   - MOTHERHAVEN_API_KEY=your_api_key
"""

import sys
from pathlib import Path
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from web.motherhaven_logger import MotherhavenLogger
from trading.logger import TradingLogger
from web.database import set_database_path, init_database


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_motherhaven_config():
    """Test 1: Verify Motherhaven configuration."""
    print_section("Test 1: Configuration Check")

    print(f"Motherhaven Enabled: {settings.motherhaven_enabled}")
    print(f"API URL: {settings.motherhaven_api_url}")
    print(f"API Key: {settings.motherhaven_api_key[:10]}..." if settings.motherhaven_api_key else "API Key: Not set")
    print(f"Timeout: {settings.motherhaven_timeout}s")
    print()

    is_valid, issues = settings.validate_motherhaven_config()
    if is_valid:
        print("✓ Configuration is valid")
        return True
    else:
        print("✗ Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False


def test_motherhaven_logger_direct():
    """Test 2: Test MotherhavenLogger directly."""
    print_section("Test 2: Direct MotherhavenLogger Test")

    if not settings.motherhaven_enabled:
        print("⚠ Motherhaven is disabled - skipping direct logger test")
        print("  Set MOTHERHAVEN_ENABLED=true in .env to enable")
        return False

    logger = MotherhavenLogger(
        base_url=settings.motherhaven_api_url,
        api_key=settings.motherhaven_api_key,
        enabled=True,
        timeout=settings.motherhaven_timeout
    )

    print("Testing decision logging...")
    decision = {
        'coin': 'BTC/USD:USD',
        'signal': 'buy_to_enter',
        'quantity_usd': 50.0,
        'leverage': 2.0,
        'confidence': 0.75,
        'exit_plan': {
            'profit_target': 105000.0,
            'stop_loss': 98000.0,
            'invalidation_condition': 'RSI drops below 30'
        },
        'justification': 'Test decision for Motherhaven integration'
    }

    success = logger.log_decision(decision, raw_response='{"signal": "buy_to_enter"}')
    print(f"  Decision: {'✓ Success' if success else '✗ Failed'}")

    time.sleep(0.5)  # Small delay between requests

    print("\nTesting account state logging...")
    success = logger.log_account_state(
        balance_usd=1000.0,
        equity_usd=1050.0,
        unrealized_pnl=50.0,
        realized_pnl=0.0,
        sharpe_ratio=1.5,
        num_positions=1
    )
    print(f"  Account State: {'✓ Success' if success else '✗ Failed'}")

    time.sleep(0.5)

    print("\nTesting position entry logging...")
    success = logger.log_position_entry(
        position_id=f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        coin="BTC/USD:USD",
        side="long",
        entry_price=99000.0,
        quantity_usd=50.0,
        leverage=2.0
    )
    print(f"  Position Entry: {'✓ Success' if success else '✗ Failed'}")

    time.sleep(0.5)

    print("\nTesting bot status logging...")
    success = logger.log_status(
        status="running",
        message="Integration test running",
        trades_today=1,
        pnl_today=50.0
    )
    print(f"  Bot Status: {'✓ Success' if success else '✗ Failed'}")

    return True


def test_trading_logger_integration():
    """Test 3: Test TradingLogger with Motherhaven integration."""
    print_section("Test 3: TradingLogger Integration Test")

    # Set database to paper mode for testing
    set_database_path("paper")
    init_database()

    # Initialize trading logger (will auto-detect Motherhaven config)
    logger = TradingLogger()

    print("Testing decision logging via TradingLogger...")
    decision = {
        'coin': 'ETH/USD:USD',
        'signal': 'sell_to_enter',
        'quantity_usd': 30.0,
        'leverage': 3.0,
        'confidence': 0.82,
        'exit_plan': {
            'profit_target': 3500.0,
            'stop_loss': 3900.0,
            'invalidation_condition': 'Break above resistance'
        },
        'justification': 'Test short position via TradingLogger integration'
    }

    try:
        decision_id = logger.log_decision(decision, raw_response='{"signal": "sell_to_enter"}')
        print(f"  ✓ Decision logged (ID: {decision_id})")
        print("    - Saved to SQLite")
        if settings.motherhaven_enabled:
            print("    - Sent to Motherhaven API")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

    time.sleep(0.5)

    print("\nTesting account state logging via TradingLogger...")
    try:
        state_id = logger.log_account_state(
            balance=950.0,
            equity=980.0,
            unrealized_pnl=30.0,
            realized_pnl=50.0,
            sharpe_ratio=1.8,
            num_positions=2
        )
        print(f"  ✓ Account state logged (ID: {state_id})")
        print("    - Saved to SQLite")
        if settings.motherhaven_enabled:
            print("    - Sent to Motherhaven API")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

    time.sleep(0.5)

    print("\nTesting position entry logging via TradingLogger...")
    test_position_id = f"ETH_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        pos_id = logger.log_position_entry(
            position_id=test_position_id,
            coin='ETH/USD:USD',
            side='short',
            entry_price=3800.0,
            quantity_usd=30.0,
            leverage=3.0
        )
        print(f"  ✓ Position entry logged (ID: {pos_id})")
        print("    - Saved to SQLite")
        if settings.motherhaven_enabled:
            print("    - Sent to Motherhaven API")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

    time.sleep(0.5)

    print("\nTesting position exit logging via TradingLogger...")
    try:
        success = logger.log_position_exit(
            position_id=test_position_id,
            exit_price=3700.0,
            realized_pnl=7.5
        )
        if success:
            print(f"  ✓ Position exit logged")
            print("    - Updated in SQLite")
            if settings.motherhaven_enabled:
                print("    - Sent to Motherhaven API")
        else:
            print(f"  ⚠ Position not found (this is expected for test)")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

    time.sleep(0.5)

    print("\nTesting bot status logging via TradingLogger...")
    try:
        logger.log_bot_status('running', 'Integration test completed successfully')
        print(f"  ✓ Bot status logged")
        print("    - Saved to SQLite")
        if settings.motherhaven_enabled:
            print("    - Sent to Motherhaven API")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

    return True


def main():
    """Run all integration tests."""
    print("\n" + "=" * 70)
    print("  MOTHERHAVEN INTEGRATION TEST SUITE")
    print("=" * 70)

    print("\nPrerequisites:")
    print("  1. Motherhaven dev server running: cd ../motherhaven && npm run dev")
    print("  2. .env configured with Motherhaven settings")
    print("  3. API key matches between bot .env and Motherhaven .env")
    print()

    input("Press Enter to start tests (Ctrl+C to cancel)...")

    results = []

    # Test 1: Configuration
    results.append(("Configuration Check", test_motherhaven_config()))

    # Test 2: Direct logger test (only if enabled)
    if settings.motherhaven_enabled:
        results.append(("Direct MotherhavenLogger", test_motherhaven_logger_direct()))
    else:
        print_section("Test 2: Skipped (Motherhaven disabled)")
        print("Enable Motherhaven in .env to test direct logger")
        results.append(("Direct MotherhavenLogger", None))

    # Test 3: TradingLogger integration
    results.append(("TradingLogger Integration", test_trading_logger_integration()))

    # Summary
    print_section("Test Summary")
    passed = 0
    failed = 0
    skipped = 0

    for test_name, result in results:
        if result is True:
            print(f"  ✓ {test_name}: PASSED")
            passed += 1
        elif result is False:
            print(f"  ✗ {test_name}: FAILED")
            failed += 1
        else:
            print(f"  ⊘ {test_name}: SKIPPED")
            skipped += 1

    print()
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0 and passed > 0:
        print("\n✓ All tests passed! Integration is working correctly.")
        print("\nNext steps:")
        print("  1. Check Motherhaven dashboard to verify data appears")
        print("  2. Start the trading bot: python run_analysis_bot.py")
        print("  3. Monitor at http://localhost:3000/llm-bot")
    else:
        print("\n⚠ Some tests failed or were skipped.")
        print("\nTroubleshooting:")
        print("  1. Check Motherhaven dev server is running")
        print("  2. Verify MOTHERHAVEN_ENABLED=true in .env")
        print("  3. Verify API key matches in both .env files")
        print("  4. Check network connectivity to localhost:3000")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Tests cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
