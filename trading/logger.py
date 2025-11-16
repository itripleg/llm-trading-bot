"""
Trading logger - convenience functions for logging bot activity to the database.

This module provides simple helper functions that the trading bot can use
to log decisions, account state, and positions without directly dealing
with database operations.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import (
    save_decision,
    save_account_state,
    save_position_entry,
    close_position,
    log_bot_status as db_log_bot_status,
    init_database
)


class TradingLogger:
    """
    Convenience class for logging trading bot activity.

    Usage:
        logger = TradingLogger()
        logger.log_decision(decision_dict, raw_response)
        logger.log_account_state(balance=1000, equity=1050, ...)
        logger.log_position_entry(...)
    """

    def __init__(self):
        """Initialize the logger and ensure database is set up."""
        init_database()

    def log_decision(
        self,
        decision: Dict[str, Any],
        raw_response: Optional[str] = None
    ) -> int:
        """
        Log a Claude trading decision.

        Args:
            decision: TradeDecision dictionary from llm/parser.py
            raw_response: Optional raw JSON string from Claude

        Returns:
            Database ID of the saved decision

        Example:
            decision_id = logger.log_decision({
                'coin': 'BTC/USDC:USDC',
                'signal': 'buy_to_enter',
                'quantity_usd': 50.0,
                'leverage': 2.0,
                'confidence': 0.75,
                'exit_plan': {...},
                'justification': '...'
            })
        """
        return save_decision(decision, raw_response)

    def log_account_state(
        self,
        balance: float,
        equity: float,
        unrealized_pnl: float = 0.0,
        realized_pnl: float = 0.0,
        sharpe_ratio: Optional[float] = None,
        num_positions: int = 0
    ) -> int:
        """
        Log current account state snapshot.

        Args:
            balance: Available cash balance in USD
            equity: Total account value (balance + positions)
            unrealized_pnl: Unrealized profit/loss from open positions
            realized_pnl: Cumulative realized profit/loss
            sharpe_ratio: Current Sharpe ratio (optional)
            num_positions: Number of open positions

        Returns:
            Database ID of the saved account state

        Example:
            state_id = logger.log_account_state(
                balance=1000.0,
                equity=1050.0,
                unrealized_pnl=50.0,
                realized_pnl=100.0,
                sharpe_ratio=1.5,
                num_positions=1
            )
        """
        return save_account_state(
            balance_usd=balance,
            equity_usd=equity,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            sharpe_ratio=sharpe_ratio,
            num_positions=num_positions
        )

    def log_position_entry(
        self,
        position_id: str,
        coin: str,
        side: str,
        entry_price: float,
        quantity_usd: float,
        leverage: float
    ) -> int:
        """
        Log a new position entry.

        Args:
            position_id: Unique identifier for this position
            coin: Trading pair (e.g., 'BTC/USDC:USDC')
            side: 'long' or 'short'
            entry_price: Entry price in USD
            quantity_usd: Position size in USD
            leverage: Leverage multiplier

        Returns:
            Database ID of the saved position

        Example:
            pos_id = logger.log_position_entry(
                position_id='BTC_20250113_001',
                coin='BTC/USDC:USDC',
                side='long',
                entry_price=99798.0,
                quantity_usd=50.0,
                leverage=2.0
            )
        """
        return save_position_entry(
            position_id=position_id,
            coin=coin,
            side=side,
            entry_price=entry_price,
            quantity_usd=quantity_usd,
            leverage=leverage
        )

    def log_position_exit(
        self,
        position_id: str,
        exit_price: float,
        realized_pnl: float
    ) -> bool:
        """
        Log a position exit/close.

        Args:
            position_id: ID of the position being closed
            exit_price: Exit price in USD
            realized_pnl: Realized profit/loss

        Returns:
            True if position was found and updated, False otherwise

        Example:
            success = logger.log_position_exit(
                position_id='BTC_20250113_001',
                exit_price=101000.0,
                realized_pnl=25.50
            )
        """
        return close_position(
            position_id=position_id,
            exit_price=exit_price,
            realized_pnl=realized_pnl
        )

    def log_bot_status(
        self,
        status: str,
        message: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Log bot status/activity.

        Args:
            status: Bot status ('running', 'paused', 'stopped', 'error')
            message: Optional message describing the status
            error: Optional error message if status is 'error'

        Example:
            logger.log_bot_status('running', 'Bot started successfully')
            logger.log_bot_status('error', error='API connection failed')
        """
        db_log_bot_status(status=status, message=message, error=error)

    def log_decision_from_trade_decision(
        self,
        trade_decision,
        raw_response: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None
    ) -> int:
        """
        Convenience method to log a TradeDecision Pydantic model directly.

        Args:
            trade_decision: TradeDecision model instance from llm/parser.py
            raw_response: Optional raw JSON string from Claude
            system_prompt: Optional system prompt sent to Claude
            user_prompt: Optional user prompt sent to Claude

        Returns:
            Database ID of the saved decision

        Example:
            from llm.parser import TradeDecision
            decision = TradeDecision(**response_dict)
            decision_id = logger.log_decision_from_trade_decision(
                decision, raw_json, system_prompt, user_prompt
            )
        """
        decision_dict = {
            'coin': trade_decision.coin,
            'signal': trade_decision.signal.value,
            'quantity_usd': trade_decision.quantity_usd,
            'leverage': trade_decision.leverage,
            'confidence': trade_decision.confidence,
            'exit_plan': {
                'profit_target': trade_decision.exit_plan.profit_target,
                'stop_loss': trade_decision.exit_plan.stop_loss,
                'invalidation_condition': trade_decision.exit_plan.invalidation_condition
            } if trade_decision.exit_plan else None,
            'justification': trade_decision.justification
        }

        return save_decision(decision_dict, raw_response, system_prompt, user_prompt)


# Singleton instance for convenience
_logger_instance = None


def get_logger() -> TradingLogger:
    """Get the singleton TradingLogger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger()
    return _logger_instance


# Convenience functions that use the singleton
def log_decision(decision: Dict[str, Any], raw_response: Optional[str] = None) -> int:
    """Convenience function to log a decision."""
    return get_logger().log_decision(decision, raw_response)


def log_account_state(
    balance: float,
    equity: float,
    unrealized_pnl: float = 0.0,
    realized_pnl: float = 0.0,
    sharpe_ratio: Optional[float] = None,
    num_positions: int = 0
) -> int:
    """Convenience function to log account state."""
    return get_logger().log_account_state(
        balance, equity, unrealized_pnl, realized_pnl, sharpe_ratio, num_positions
    )


def log_position_entry(
    position_id: str,
    coin: str,
    side: str,
    entry_price: float,
    quantity_usd: float,
    leverage: float
) -> int:
    """Convenience function to log position entry."""
    return get_logger().log_position_entry(
        position_id, coin, side, entry_price, quantity_usd, leverage
    )


def log_position_exit(position_id: str, exit_price: float, realized_pnl: float) -> bool:
    """Convenience function to log position exit."""
    return get_logger().log_position_exit(position_id, exit_price, realized_pnl)


def log_bot_status(status: str, message: Optional[str] = None, error: Optional[str] = None):
    """Convenience function to log bot status."""
    get_logger().log_bot_status(status, message, error)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("Testing TradingLogger...")

    logger = TradingLogger()

    # Test logging a decision
    print("\n1. Testing decision logging...")
    decision_id = logger.log_decision({
        'coin': 'ETH/USDC:USDC',
        'signal': 'buy_to_enter',
        'quantity_usd': 30.0,
        'leverage': 3.0,
        'confidence': 0.82,
        'exit_plan': {
            'profit_target': 4200.0,
            'stop_loss': 3900.0,
            'invalidation_condition': 'Break below support'
        },
        'justification': 'ETH showing strong momentum with bullish divergence'
    }, raw_response='{"coin": "ETH/USDC:USDC", ...}')
    print(f"[OK] Logged decision with ID: {decision_id}")

    # Test logging account state
    print("\n2. Testing account state logging...")
    state_id = logger.log_account_state(
        balance=950.0,
        equity=980.0,
        unrealized_pnl=30.0,
        realized_pnl=50.0,
        sharpe_ratio=1.8,
        num_positions=2
    )
    print(f"[OK] Logged account state with ID: {state_id}")

    # Test logging position entry
    print("\n3. Testing position entry logging...")
    from datetime import datetime
    test_position_id = f"ETH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pos_id = logger.log_position_entry(
        position_id=test_position_id,
        coin='ETH/USDC:USDC',
        side='long',
        entry_price=4000.0,
        quantity_usd=30.0,
        leverage=3.0
    )
    print(f"[OK] Logged position entry with ID: {pos_id}")

    # Test logging position exit
    print("\n4. Testing position exit logging...")
    success = logger.log_position_exit(
        position_id=test_position_id,
        exit_price=4100.0,
        realized_pnl=7.5
    )
    print(f"[OK] Logged position exit: {success}")

    # Test logging bot status
    print("\n5. Testing bot status logging...")
    logger.log_bot_status('running', 'Trading loop iteration completed')
    print("[OK] Logged bot status")

    # Test convenience functions
    print("\n6. Testing convenience functions...")
    log_bot_status('running', 'Testing convenience function')
    print("[OK] Convenience functions work")

    print("\n[OK] All TradingLogger tests passed!")
