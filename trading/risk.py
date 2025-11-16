"""
Risk management and trade validation.

This module enforces all trading safety limits before trades are executed.
Critical for preventing catastrophic losses in live trading.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from llm.parser import TradeDecision, TradeSignal
from trading.account import TradingAccount, Position
from web.database import get_closed_positions

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Enforces all trading safety limits.

    Validates trades against:
    - Maximum position size
    - Maximum leverage
    - Daily loss limits
    - Available balance
    - Liquidation risk
    - Portfolio exposure
    """

    def __init__(self, account: TradingAccount):
        """
        Initialize risk manager.

        Args:
            account: Trading account instance to monitor
        """
        self.account = account
        self.settings = settings

    def validate_trade(
        self,
        decision: TradeDecision,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Validate a trade decision against all safety limits.

        Args:
            decision: Parsed trade decision from LLM
            current_price: Current market price of the asset

        Returns:
            Tuple of (is_valid, rejection_reason)
            - is_valid: True if trade passes all checks
            - rejection_reason: Empty string if valid, otherwise detailed reason for rejection
        """
        # 1. HOLD signals are always allowed
        if decision.signal == TradeSignal.HOLD:
            return True, ""

        # 2. CLOSE signals - validate position exists
        if decision.signal == TradeSignal.CLOSE:
            return self._validate_close_signal(decision)

        # 3. ENTRY signals - comprehensive validation
        if decision.is_entry():
            return self._validate_entry_signal(decision, current_price)

        return False, "Unknown signal type"

    def _validate_close_signal(self, decision: TradeDecision) -> Tuple[bool, str]:
        """Validate a close position signal."""
        # Check if position exists
        if decision.coin not in self.account.positions:
            return False, f"Cannot close {decision.coin}: no open position exists"

        return True, ""

    def _validate_entry_signal(
        self,
        decision: TradeDecision,
        current_price: float
    ) -> Tuple[bool, str]:
        """Validate an entry (buy/sell) signal against all safety limits."""

        # Check 1: Position size limit
        if decision.quantity_usd > self.settings.max_position_size_usd:
            return False, (
                f"Position size ${decision.quantity_usd:.2f} exceeds maximum "
                f"${self.settings.max_position_size_usd:.2f}"
            )

        # Check 2: Leverage limit
        if decision.leverage > self.settings.max_leverage:
            return False, (
                f"Leverage {decision.leverage}x exceeds maximum "
                f"{self.settings.max_leverage}x"
            )

        # Check 3: Minimum position size (avoid dust positions)
        if decision.quantity_usd < 1.0:
            return False, f"Position size ${decision.quantity_usd:.2f} too small (minimum $1.00)"

        # Check 4: Available balance
        available = self.account.get_available_balance()
        if decision.quantity_usd > available:
            return False, (
                f"Insufficient balance: need ${decision.quantity_usd:.2f}, "
                f"available ${available:.2f}"
            )

        # Check 5: Daily loss limit
        daily_pnl = self.get_daily_realized_pnl()
        if daily_pnl < -self.settings.daily_loss_limit_usd:
            return False, (
                f"Daily loss limit exceeded: ${abs(daily_pnl):.2f} lost today "
                f"(limit: ${self.settings.daily_loss_limit_usd:.2f}). "
                f"Trading halted until next day."
            )

        # Check 6: Position already exists for this coin
        if decision.coin in self.account.positions:
            return False, (
                f"Position already open for {decision.coin}. "
                f"Close existing position before opening new one."
            )

        # Check 7: Liquidation risk warning (calculate would-be liquidation price)
        side = 'long' if decision.signal == TradeSignal.BUY_TO_ENTER else 'short'
        liq_price = self.calculate_liquidation_price(
            entry_price=current_price,
            leverage=decision.leverage,
            side=side
        )

        # Warn if liquidation price is very close (within 10%)
        price_to_liq_pct = abs(liq_price - current_price) / current_price * 100
        if price_to_liq_pct < 10:
            logger.warning(
                f"⚠️  HIGH LIQUIDATION RISK: {decision.coin} {side} {decision.leverage}x "
                f"will liquidate at ${liq_price:.2f} ({price_to_liq_pct:.1f}% from entry)"
            )
            # Allow but warn - don't block the trade

        # Check 8: Leverage sanity check with stop-loss
        if decision.exit_plan.stop_loss:
            potential_loss_pct = self._calculate_stop_loss_distance_pct(
                entry_price=current_price,
                stop_loss=decision.exit_plan.stop_loss,
                side=side
            )

            # With leverage, a 5% move becomes 5% * leverage loss on capital
            leveraged_loss_pct = potential_loss_pct * decision.leverage

            # Warn if stop-loss would cause >50% capital loss
            if leveraged_loss_pct > 50:
                logger.warning(
                    f"⚠️  DANGEROUS STOP-LOSS: {decision.coin} stop at "
                    f"${decision.exit_plan.stop_loss:.2f} could lose "
                    f"{leveraged_loss_pct:.1f}% of position capital"
                )

        # All checks passed
        return True, ""

    def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        side: str
    ) -> float:
        """
        Calculate liquidation price for a position.

        Liquidation occurs when loss reaches 100% of initial margin.
        With leverage, a small price move can cause large % loss on margin.

        Args:
            entry_price: Entry price of position
            leverage: Leverage multiplier
            side: 'long' or 'short'

        Returns:
            Liquidation price

        Example:
            Long position with 5x leverage:
            - Entry: $100
            - Leverage: 5x
            - Initial margin: $20 (for $100 position size)
            - Liquidates when price drops 20% → $80
            - Formula: $100 * (1 - 1/5) = $80
        """
        if leverage <= 0:
            raise ValueError("Leverage must be positive")

        # Liquidation happens when loss = 100% of margin
        # Margin is 1/leverage of position size
        # So liquidation is at (1/leverage)% price move against position

        liquidation_threshold = 1.0 / leverage  # e.g., 5x → 0.2 (20%)

        if side == 'long':
            # Long liquidates when price drops by threshold
            liq_price = entry_price * (1 - liquidation_threshold)
        else:  # short
            # Short liquidates when price rises by threshold
            liq_price = entry_price * (1 + liquidation_threshold)

        return liq_price

    def is_approaching_liquidation(
        self,
        position: Position,
        current_price: float,
        threshold_pct: float = 20.0
    ) -> bool:
        """
        Check if a position is approaching liquidation.

        Args:
            position: Open position to check
            current_price: Current market price
            threshold_pct: Alert if within this % of liquidation (default 20%)

        Returns:
            True if within threshold of liquidation
        """
        liq_price = self.calculate_liquidation_price(
            entry_price=position.entry_price,
            leverage=position.leverage,
            side=position.side
        )

        # Calculate distance to liquidation as % of current price
        distance_to_liq = abs(liq_price - current_price) / current_price * 100

        return distance_to_liq < threshold_pct

    def get_daily_realized_pnl(self) -> float:
        """
        Calculate total realized P&L for today.

        Queries database for all positions closed today and sums their realized P&L.
        Used to enforce daily loss limits.

        Returns:
            Total realized P&L for today (negative = loss)
        """
        try:
            # Get all closed positions (we'll filter for today)
            closed_positions = get_closed_positions(limit=500)

            # Get today's date boundaries (UTC)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            daily_pnl = 0.0
            positions_today = 0

            for pos in closed_positions:
                # Parse exit_time (ISO format)
                if pos.get('exit_time'):
                    exit_time = datetime.fromisoformat(pos['exit_time'])

                    # Check if closed today
                    if today_start <= exit_time < today_end:
                        pnl = pos.get('realized_pnl', 0.0)
                        daily_pnl += pnl
                        positions_today += 1

            if positions_today > 0:
                logger.info(
                    f"Daily P&L: ${daily_pnl:.2f} from {positions_today} closed position(s)"
                )

            return daily_pnl

        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            # Return 0 on error (conservative - don't block trading on database errors)
            return 0.0

    def get_portfolio_exposure(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio exposure (sum of all position sizes * leverage).

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            Total notional exposure in USD
        """
        total_exposure = 0.0

        for coin, position in self.account.positions.items():
            # Notional value = quantity * leverage
            notional = position.quantity_usd * position.leverage
            total_exposure += notional

        return total_exposure

    def check_all_positions_for_liquidation(
        self,
        current_prices: Dict[str, float]
    ) -> List[Dict[str, any]]:
        """
        Check all open positions for liquidation risk.

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            List of positions at risk with details
        """
        at_risk = []

        for coin, position in self.account.positions.items():
            current_price = current_prices.get(coin)
            if not current_price:
                continue

            if self.is_approaching_liquidation(position, current_price):
                liq_price = self.calculate_liquidation_price(
                    entry_price=position.entry_price,
                    leverage=position.leverage,
                    side=position.side
                )

                distance = abs(liq_price - current_price) / current_price * 100
                unrealized_pnl = position.calculate_pnl(current_price)

                at_risk.append({
                    'coin': coin,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'current_price': current_price,
                    'liquidation_price': liq_price,
                    'distance_to_liq_pct': distance,
                    'leverage': position.leverage,
                    'unrealized_pnl': unrealized_pnl,
                    'position_id': position.position_id
                })

        return at_risk

    def _calculate_stop_loss_distance_pct(
        self,
        entry_price: float,
        stop_loss: float,
        side: str
    ) -> float:
        """
        Calculate distance from entry to stop-loss as percentage.

        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            side: 'long' or 'short'

        Returns:
            Percentage distance (always positive)
        """
        if side == 'long':
            # Long: stop below entry
            distance_pct = (entry_price - stop_loss) / entry_price * 100
        else:
            # Short: stop above entry
            distance_pct = (stop_loss - entry_price) / entry_price * 100

        return abs(distance_pct)

    def get_risk_summary(self, current_prices: Dict[str, float]) -> Dict[str, any]:
        """
        Generate comprehensive risk summary for dashboard/monitoring.

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            Dict with risk metrics
        """
        daily_pnl = self.get_daily_realized_pnl()
        available_balance = self.account.get_available_balance()
        total_exposure = self.get_portfolio_exposure(current_prices)
        at_risk_positions = self.check_all_positions_for_liquidation(current_prices)

        # Calculate daily loss limit remaining
        daily_loss_remaining = self.settings.daily_loss_limit_usd + daily_pnl  # pnl is negative for losses
        daily_loss_used_pct = (abs(daily_pnl) / self.settings.daily_loss_limit_usd * 100) if daily_pnl < 0 else 0

        # Check if trading is halted
        trading_halted = daily_pnl < -self.settings.daily_loss_limit_usd

        return {
            'daily_pnl': daily_pnl,
            'daily_loss_limit': self.settings.daily_loss_limit_usd,
            'daily_loss_remaining': max(0, daily_loss_remaining),
            'daily_loss_used_pct': min(100, daily_loss_used_pct),
            'trading_halted': trading_halted,
            'available_balance': available_balance,
            'total_exposure': total_exposure,
            'max_position_size': self.settings.max_position_size_usd,
            'max_leverage': self.settings.max_leverage,
            'num_positions': len(self.account.positions),
            'positions_at_risk': len(at_risk_positions),
            'at_risk_details': at_risk_positions
        }


# Module-level convenience functions
def validate_trade_decision(
    decision: TradeDecision,
    account: TradingAccount,
    current_price: float
) -> Tuple[bool, str]:
    """
    Convenience function to validate a trade decision.

    Args:
        decision: Trade decision from LLM
        account: Trading account
        current_price: Current market price

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    risk_manager = RiskManager(account)
    return risk_manager.validate_trade(decision, current_price)


def calculate_liquidation_price(entry_price: float, leverage: float, side: str) -> float:
    """
    Convenience function to calculate liquidation price.

    Args:
        entry_price: Position entry price
        leverage: Leverage multiplier
        side: 'long' or 'short'

    Returns:
        Liquidation price
    """
    # Create temporary account just for calculation
    from trading.account import TradingAccount
    temp_account = TradingAccount(initial_balance=1000)
    risk_manager = RiskManager(temp_account)
    return risk_manager.calculate_liquidation_price(entry_price, leverage, side)


if __name__ == "__main__":
    """Test risk manager functionality."""
    print("Testing Risk Manager...")
    print("=" * 60)

    # Test liquidation price calculations
    print("\n1. LIQUIDATION PRICE CALCULATIONS:")
    print("-" * 60)

    test_cases = [
        ("Long", 100.0, 5.0, "long"),
        ("Long", 100.0, 10.0, "long"),
        ("Long", 100.0, 2.0, "long"),
        ("Short", 100.0, 5.0, "short"),
        ("Short", 100.0, 10.0, "short"),
    ]

    for name, entry, lev, side in test_cases:
        liq = calculate_liquidation_price(entry, lev, side)
        distance = abs(liq - entry) / entry * 100
        print(f"{name:10} Entry: ${entry:7.2f}  Leverage: {lev:4.1f}x  "
              f"Liquidation: ${liq:7.2f}  ({distance:.1f}% away)")

    print("\n2. RISK VALIDATION EXAMPLES:")
    print("-" * 60)

    # Create test account
    from trading.account import TradingAccount
    from llm.parser import TradeDecision, TradeSignal, ExitPlan

    account = TradingAccount(initial_balance=1000.0)
    risk_manager = RiskManager(account)

    # Test case 1: Valid trade
    decision1 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=30.0,
        leverage=3.0,
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="Valid test trade within limits"
    )

    valid, reason = risk_manager.validate_trade(decision1, 100000.0)
    print(f"\nTest 1 - Valid trade ($30, 3x leverage):")
    print(f"  Result: {'✅ APPROVED' if valid else '❌ REJECTED'}")
    if reason:
        print(f"  Reason: {reason}")

    # Test case 2: Oversized position
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
    print(f"\nTest 2 - Oversized position ($100, max is $50):")
    print(f"  Result: {'✅ APPROVED' if valid else '❌ REJECTED'}")
    if reason:
        print(f"  Reason: {reason}")

    # Test case 3: Excessive leverage
    decision3 = TradeDecision(
        coin="BTC/USD:USD",
        signal=TradeSignal.BUY_TO_ENTER,
        quantity_usd=30.0,
        leverage=15.0,  # Exceeds max_leverage (5)
        confidence=0.8,
        exit_plan=ExitPlan(profit_target=105000, stop_loss=95000),
        justification="High leverage test"
    )

    valid, reason = risk_manager.validate_trade(decision3, 100000.0)
    print(f"\nTest 3 - Excessive leverage (15x, max is 5x):")
    print(f"  Result: {'✅ APPROVED' if valid else '❌ REJECTED'}")
    if reason:
        print(f"  Reason: {reason}")

    print("\n3. RISK SUMMARY:")
    print("-" * 60)

    summary = risk_manager.get_risk_summary({'BTC/USD:USD': 100000.0})
    print(f"Daily P&L: ${summary['daily_pnl']:.2f}")
    print(f"Daily Loss Limit: ${summary['daily_loss_limit']:.2f}")
    print(f"Available Balance: ${summary['available_balance']:.2f}")
    print(f"Max Position Size: ${summary['max_position_size']:.2f}")
    print(f"Max Leverage: {summary['max_leverage']}x")
    print(f"Trading Halted: {summary['trading_halted']}")

    print("\n" + "=" * 60)
    print("✅ Risk Manager tests complete!")
