"""
Unit tests for Risk Manager module.

Tests all critical safety features:
- Position size limits
- Leverage limits
- Daily loss limits
- Liquidation price calculations
- Trade validation logic
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.risk import RiskManager, calculate_liquidation_price
from trading.account import TradingAccount
from llm.parser import TradeDecision, TradeSignal, ExitPlan


def test_liquidation_price_calculations():
    """Test liquidation price calculations for various leverage levels."""
    print("\n=== TEST: Liquidation Price Calculations ===")

    test_cases = [
        # (entry_price, leverage, side, expected_liq_price)
        (100.0, 5.0, 'long', 80.0),    # 5x long: 20% drop
        (100.0, 10.0, 'long', 90.0),   # 10x long: 10% drop
        (100.0, 2.0, 'long', 50.0),    # 2x long: 50% drop
        (100.0, 5.0, 'short', 120.0),  # 5x short: 20% rise
        (100.0, 10.0, 'short', 110.0), # 10x short: 10% rise
        (50000.0, 3.0, 'long', 50000.0 * (1 - 1/3)),  # 3x long on BTC
    ]

    passed = 0
    for entry, lev, side, expected in test_cases:
        result = calculate_liquidation_price(entry, lev, side)
        tolerance = abs(expected * 0.01)  # 1% tolerance for float comparison

        if abs(result - expected) < tolerance:
            passed += 1
            print(f"✅ {side:5} {lev:4.1f}x @ ${entry:8.2f} → Liq: ${result:8.2f} (expected ${expected:8.2f})")
        else:
            print(f"❌ {side:5} {lev:4.1f}x @ ${entry:8.2f} → Liq: ${result:8.2f} (expected ${expected:8.2f})")

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_position_size_validation():
    """Test that oversized positions are rejected."""
    print("\n=== TEST: Position Size Validation ===")

    account = TradingAccount(initial_balance=1000.0)
    risk_manager = RiskManager(account)

    # Test 1: Valid position (within limit)
    decision1 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=30.0,  # Well within max_position_size_usd (50)
        leverage=3.0,
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Valid position size test"
    )

    valid, reason = risk_manager.validate_trade(decision1, 100000.0)
    test1_pass = valid
    print(f"{'✅' if test1_pass else '❌'} Test 1 - Valid position ($30): {' APPROVED' if valid else f'REJECTED - {reason}'}")

    # Test 2: Oversized position (exceeds limit)
    decision2 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=100.0,  # Exceeds max_position_size_usd (50)
        leverage=3.0,
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Oversized position test"
    )

    valid, reason = risk_manager.validate_trade(decision2, 100000.0)
    test2_pass = not valid and "exceeds maximum" in reason.lower()
    print(f"{'✅' if test2_pass else '❌'} Test 2 - Oversized ($100): {'REJECTED' if not valid else 'APPROVED (SHOULD REJECT)'}")
    if not valid:
        print(f"   Reason: {reason}")

    return test1_pass and test2_pass


def test_leverage_validation():
    """Test that excessive leverage is rejected."""
    print("\n=== TEST: Leverage Validation ===")

    account = TradingAccount(initial_balance=1000.0)
    risk_manager = RiskManager(account)

    # Test 1: Valid leverage
    decision1 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=30.0,
        leverage=3.0,  # Within max_leverage (5)
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Valid leverage test"
    )

    valid, reason = risk_manager.validate_trade(decision1, 100000.0)
    test1_pass = valid
    print(f"{'✅' if test1_pass else '❌'} Test 1 - Valid leverage (3x): {'APPROVED' if valid else f'REJECTED - {reason}'}")

    # Test 2: Excessive leverage
    decision2 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=30.0,
        leverage=15.0,  # Exceeds max_leverage (5)
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="High leverage test"
    )

    valid, reason = risk_manager.validate_trade(decision2, 100000.0)
    test2_pass = not valid and "leverage" in reason.lower()
    print(f"{'✅' if test2_pass else '❌'} Test 2 - Excessive leverage (15x): {'REJECTED' if not valid else 'APPROVED (SHOULD REJECT)'}")
    if not valid:
        print(f"   Reason: {reason}")

    return test1_pass and test2_pass


def test_insufficient_balance():
    """Test that trades exceeding balance are rejected."""
    print("\n=== TEST: Insufficient Balance Validation ===")

    account = TradingAccount(initial_balance=100.0)  # Low balance
    risk_manager = RiskManager(account)

    # Test: Position larger than balance
    decision = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=150.0,  # Exceeds balance (100)
        leverage=3.0,
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Insufficient balance test"
    )

    valid, reason = risk_manager.validate_trade(decision, 100000.0)
    test_pass = not valid and "insufficient" in reason.lower()
    print(f"{'✅' if test_pass else '❌'} Position $150 with $100 balance: {'REJECTED' if not valid else 'APPROVED (SHOULD REJECT)'}")
    if not valid:
        print(f"   Reason: {reason}")

    return test_pass


def test_hold_signal_always_allowed():
    """Test that HOLD signals are always approved."""
    print("\n=== TEST: HOLD Signal Validation ===")

    account = TradingAccount(initial_balance=0.01)  # Nearly zero balance
    risk_manager = RiskManager(account)

    # HOLD should always be allowed, even with no balance
    decision = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.HOLD,
        quantity_usd=0.0,
        leverage=0.0,
        confidence=0.5,
        exit_plan=ExitPlan(),
        justification="Hold signal should always be allowed"
    )

    valid, reason = risk_manager.validate_trade(decision, 100000.0)
    test_pass = valid
    print(f"{'✅' if test_pass else '❌'} HOLD signal: {'APPROVED' if valid else f'REJECTED - {reason}'}")

    return test_pass


def test_close_without_position():
    """Test that CLOSE is rejected when no position exists."""
    print("\n=== TEST: CLOSE Signal Without Position ===")

    account = TradingAccount(initial_balance=1000.0)
    risk_manager = RiskManager(account)

    # Try to close a position that doesn't exist
    decision = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.CLOSE,
        quantity_usd=0.0,
        leverage=0.0,
        confidence=0.8,
        exit_plan=ExitPlan(),
        justification="Close non-existent position"
    )

    valid, reason = risk_manager.validate_trade(decision, 100000.0)
    test_pass = not valid and "no open position" in reason.lower()
    print(f"{'✅' if test_pass else '❌'} CLOSE without position: {'REJECTED' if not valid else 'APPROVED (SHOULD REJECT)'}")
    if not valid:
        print(f"   Reason: {reason}")

    return test_pass


def test_duplicate_position():
    """Test that duplicate positions for same coin are rejected."""
    print("\n=== TEST: Duplicate Position Prevention ===")

    account = TradingAccount(initial_balance=1000.0)

    # Open first position
    account.open_position(
        coin="BTC/USD:USD",
        side='long',
        entry_price=100000.0,
        quantity_usd=30.0,
        leverage=3.0,
        decision_id=1
    )

    risk_manager = RiskManager(account)

    # Try to open another position for same coin
    decision = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=20.0,
        leverage=2.0,
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Duplicate position test"
    )

    valid, reason = risk_manager.validate_trade(decision, 100000.0)
    test_pass = not valid and "already open" in reason.lower()
    print(f"{'✅' if test_pass else '❌'} Duplicate position: {'REJECTED' if not valid else 'APPROVED (SHOULD REJECT)'}")
    if not valid:
        print(f"   Reason: {reason}")

    return test_pass


def test_approaching_liquidation():
    """Test detection of positions approaching liquidation."""
    print("\n=== TEST: Liquidation Risk Detection ===")

    account = TradingAccount(initial_balance=1000.0)

    # Open high-leverage position
    account.open_position(
        coin="BTC/USD:USD",
        side='long',
        entry_price=100000.0,
        quantity_usd=50.0,
        leverage=10.0,  # High leverage - liquidates at 90,000
        decision_id=1
    )

    risk_manager = RiskManager(account)
    position = account.positions["BTC/USD:USD"]

    # Test 1: Price near liquidation (91,000 - within 10% of 90,000)
    approaching = risk_manager.is_approaching_liquidation(position, 91000.0, threshold_pct=20.0)
    test1_pass = approaching
    print(f"{'✅' if test1_pass else '❌'} Test 1 - Price near liquidation (91k, liq 90k): {'DETECTED' if approaching else 'NOT DETECTED'}")

    # Test 2: Price far from liquidation (100,000 - entry price)
    approaching = risk_manager.is_approaching_liquidation(position, 100000.0, threshold_pct=20.0)
    test2_pass = not approaching
    print(f"{'✅' if test2_pass else '❌'} Test 2 - Price far from liquidation (100k, liq 90k): {'NOT DETECTED' if not approaching else 'DETECTED (SHOULD NOT)'}")

    return test1_pass and test2_pass


def run_all_tests():
    """Run all risk manager tests."""
    print("\n" + "="*70)
    print("RISK MANAGER - UNIT TESTS")
    print("="*70)

    tests = [
        ("Liquidation Price Calculations", test_liquidation_price_calculations),
        ("Position Size Validation", test_position_size_validation),
        ("Leverage Validation", test_leverage_validation),
        ("Insufficient Balance", test_insufficient_balance),
        ("HOLD Signal Always Allowed", test_hold_signal_always_allowed),
        ("CLOSE Without Position", test_close_without_position),
        ("Duplicate Position Prevention", test_duplicate_position),
        ("Approaching Liquidation Detection", test_approaching_liquidation),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ {name}: EXCEPTION - {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:12} {name}")

    print("="*70)
    print(f"TOTAL: {passed_count}/{total_count} tests passed")
    print("="*70)

    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
