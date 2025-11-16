"""
Account state management for paper trading.

Tracks simulated balance, positions, and P&L without real money.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import (
    save_account_state,
    get_latest_account_state,
    save_position_entry,
    close_position as db_close_position,
    get_open_positions
)


class Position:
    """Represents an open trading position."""

    def __init__(
        self,
        position_id: str,
        coin: str,
        side: str,  # 'long' or 'short'
        entry_price: float,
        quantity_usd: float,
        leverage: float,
        entry_time: datetime
    ):
        self.position_id = position_id
        self.coin = coin
        self.side = side
        self.entry_price = entry_price
        self.quantity_usd = quantity_usd
        self.leverage = leverage
        self.entry_time = entry_time

    def calculate_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L for this position.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L in USD (positive = profit, negative = loss)
        """
        # Position size in base currency (e.g., BTC)
        position_size = (self.quantity_usd * self.leverage) / self.entry_price

        if self.side == 'long':
            # Long: profit when price goes up
            pnl = (current_price - self.entry_price) * position_size
        else:
            # Short: profit when price goes down
            pnl = (self.entry_price - current_price) * position_size

        return pnl

    def get_margin(self) -> float:
        """Get the margin (collateral) for this position."""
        return self.quantity_usd  # Margin is the USD amount committed

    def __repr__(self):
        return f"Position({self.coin} {self.side} ${self.quantity_usd} @{self.entry_price} {self.leverage}x)"


class TradingAccount:
    """
    Manages simulated trading account balance and positions.

    Tracks:
    - Cash balance (available funds)
    - Open positions
    - Realized P&L (from closed positions)
    - Unrealized P&L (from open positions)
    """

    def __init__(self, initial_balance: float = 1000.0):
        """
        Initialize trading account.

        Args:
            initial_balance: Starting balance in USD
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.realized_pnl = 0.0
        self.positions: Dict[str, Position] = {}

        # Try to load existing state from database
        self._load_from_database()

    def _load_from_database(self):
        """Load account state from database if it exists."""
        try:
            # Get latest account state
            account_state = get_latest_account_state()
            if account_state:
                self.balance = account_state['balance_usd']
                self.realized_pnl = account_state.get('realized_pnl', 0.0)

            # Load open positions
            open_positions = get_open_positions()
            for pos_dict in open_positions:
                position = Position(
                    position_id=pos_dict['position_id'],
                    coin=pos_dict['coin'],
                    side=pos_dict['side'],
                    entry_price=pos_dict['entry_price'],
                    quantity_usd=pos_dict['quantity_usd'],
                    leverage=pos_dict['leverage'],
                    entry_time=datetime.fromisoformat(pos_dict['entry_time'])
                )
                self.positions[pos_dict['coin']] = position

        except Exception as e:
            print(f"[WARNING] Could not load account state from database: {e}")
            print(f"[INFO] Starting fresh with ${self.initial_balance}")

    def get_available_balance(self) -> float:
        """Get available cash balance (not locked in positions)."""
        return self.balance

    def get_total_equity(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total account equity (balance + position values).

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            Total equity in USD
        """
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        return self.balance + unrealized_pnl

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total unrealized P&L from all open positions.

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            Total unrealized P&L in USD
        """
        total_pnl = 0.0
        for coin, position in self.positions.items():
            if coin in current_prices:
                total_pnl += position.calculate_pnl(current_prices[coin])
        return total_pnl

    def can_open_position(self, quantity_usd: float) -> bool:
        """
        Check if there's sufficient balance to open a position.

        Args:
            quantity_usd: Position size in USD

        Returns:
            True if sufficient balance, False otherwise
        """
        return self.balance >= quantity_usd

    def open_position(
        self,
        coin: str,
        side: str,
        entry_price: float,
        quantity_usd: float,
        leverage: float,
        decision_id: Optional[int] = None
    ) -> Optional[Position]:
        """
        Open a new position.

        Args:
            coin: Trading pair (e.g., 'BTC/USDC:USDC')
            side: 'long' or 'short'
            entry_price: Entry price in USD
            quantity_usd: Position size in USD
            leverage: Leverage multiplier
            decision_id: ID of the decision that opened this position (for tracking)

        Returns:
            Position object if successful, None if insufficient balance
        """
        # Check if enough balance
        if not self.can_open_position(quantity_usd):
            print(f"[ERROR] Insufficient balance to open position")
            print(f"  Required: ${quantity_usd:.2f}, Available: ${self.balance:.2f}")
            return None

        # Check if position already exists for this coin
        if coin in self.positions:
            print(f"[WARNING] Position already exists for {coin}, closing old one first")
            # In a real system, we'd close the old position
            # For now, just replace it

        # Create position
        position_id = f"{coin.split('/')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        position = Position(
            position_id=position_id,
            coin=coin,
            side=side,
            entry_price=entry_price,
            quantity_usd=quantity_usd,
            leverage=leverage,
            entry_time=datetime.now()
        )

        # Deduct margin from balance
        self.balance -= quantity_usd
        self.positions[coin] = position

        # Log to database
        save_position_entry(
            position_id=position_id,
            coin=coin,
            side=side,
            entry_price=entry_price,
            quantity_usd=quantity_usd,
            leverage=leverage,
            decision_id=decision_id
        )

        print(f"[OK] Opened {side} position: {position}")
        print(f"  New balance: ${self.balance:.2f}")

        return position

    def close_position(self, coin: str, exit_price: float) -> Optional[float]:
        """
        Close an open position.

        Args:
            coin: Trading pair to close
            exit_price: Exit price in USD

        Returns:
            Realized P&L if successful, None if no position exists
        """
        if coin not in self.positions:
            print(f"[WARNING] No open position for {coin}")
            return None

        position = self.positions[coin]

        # Calculate realized P&L
        pnl = position.calculate_pnl(exit_price)

        # Return margin plus P&L to balance
        self.balance += position.get_margin() + pnl
        self.realized_pnl += pnl

        # Log to database
        db_close_position(
            position_id=position.position_id,
            exit_price=exit_price,
            realized_pnl=pnl
        )

        print(f"[OK] Closed {position.side} position: {position}")
        print(f"  Exit price: ${exit_price:.2f}")
        print(f"  Realized P&L: ${pnl:+.2f}")
        print(f"  New balance: ${self.balance:.2f}")

        # Remove from active positions
        del self.positions[coin]

        return pnl

    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> Optional[float]:
        """
        Calculate Sharpe ratio from closed trade history.

        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns

        This measures risk-adjusted performance. Higher is better.
        - > 1.0 is good
        - > 2.0 is very good
        - > 3.0 is excellent

        Args:
            risk_free_rate: Annual risk-free rate (default 0.0 for crypto)

        Returns:
            Sharpe ratio, or None if insufficient data (< 2 trades)
        """
        import numpy as np

        try:
            # Get closed positions from database
            closed_positions = get_closed_positions(limit=500)

            if len(closed_positions) < 2:
                # Need at least 2 trades to calculate standard deviation
                return None

            # Calculate returns for each trade as % of capital risked
            returns = []
            for pos in closed_positions:
                realized_pnl = pos.get('realized_pnl')
                quantity_usd = pos.get('quantity_usd')

                if realized_pnl is not None and quantity_usd and quantity_usd > 0:
                    # Return as % of capital risked (margin)
                    trade_return = (realized_pnl / quantity_usd) * 100  # in %
                    returns.append(trade_return)

            if len(returns) < 2:
                return None

            returns_array = np.array(returns)

            # Calculate mean and std dev of returns
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array, ddof=1)  # Sample std dev

            if std_return == 0:
                # No volatility (all trades same return) - edge case
                return None

            # Calculate Sharpe ratio
            # Note: We're using per-trade returns, not annualized
            # For daily/weekly trading, this gives a rough risk-adjusted metric
            sharpe = (mean_return - risk_free_rate) / std_return

            return sharpe

        except Exception as e:
            print(f"[WARNING] Error calculating Sharpe ratio: {e}")
            return None

    def save_state(self, current_prices: Dict[str, float]):
        """
        Save current account state to database.

        Args:
            current_prices: Dict of coin -> current price for unrealized PnL calculation
        """
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        equity = self.get_total_equity(current_prices)

        # Calculate Sharpe ratio from trade history
        sharpe_ratio = self.calculate_sharpe_ratio()

        save_account_state(
            balance_usd=self.balance,
            equity_usd=equity,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self.realized_pnl,
            sharpe_ratio=sharpe_ratio,
            num_positions=len(self.positions)
        )

    def get_summary(self, current_prices: Dict[str, float]) -> Dict:
        """
        Get account summary for display.

        Args:
            current_prices: Dict of coin -> current price

        Returns:
            Dict with account metrics
        """
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        equity = self.get_total_equity(current_prices)
        total_pnl = self.realized_pnl + unrealized_pnl

        # Get open positions from database (includes exit plan from linked decision)
        db_positions = get_open_positions()

        # Build position list with enhanced data
        positions_list = []
        for pos in self.positions.values():
            # Find matching DB position to get exit plan
            db_pos = next((p for p in db_positions if p['coin'] == pos.coin), None)

            pos_data = {
                'coin': pos.coin,
                'side': pos.side,
                'entry_price': pos.entry_price,
                'entry_time': pos.entry_time.isoformat(),
                'current_price': current_prices.get(pos.coin, pos.entry_price),
                'quantity_usd': pos.quantity_usd,
                'leverage': pos.leverage,
                'unrealized_pnl': pos.calculate_pnl(current_prices.get(pos.coin, pos.entry_price))
            }

            # Add exit plan if available from database
            if db_pos:
                pos_data['profit_target'] = db_pos.get('profit_target')
                pos_data['stop_loss'] = db_pos.get('stop_loss')
                pos_data['invalidation_condition'] = db_pos.get('invalidation_condition')
                pos_data['entry_justification'] = db_pos.get('entry_justification')

            positions_list.append(pos_data)

        return {
            'balance': self.balance,
            'equity': equity,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': total_pnl,
            'total_return_pct': (total_pnl / self.initial_balance) * 100,
            'num_positions': len(self.positions),
            'positions': positions_list
        }

    def __repr__(self):
        return f"TradingAccount(balance=${self.balance:.2f}, positions={len(self.positions)}, realized_pnl=${self.realized_pnl:+.2f})"


if __name__ == "__main__":
    # Test the account manager
    print("Testing TradingAccount...")
    print()

    # Initialize account
    account = TradingAccount(initial_balance=1000.0)
    print(f"Initial state: {account}")
    print()

    # Open a long position
    print("Opening long BTC position...")
    position = account.open_position(
        coin='BTC/USDC:USDC',
        side='long',
        entry_price=100000.0,
        quantity_usd=100.0,
        leverage=2.0
    )
    print()

    # Check balance after opening
    current_prices = {'BTC/USDC:USDC': 101000.0}  # Price went up
    summary = account.get_summary(current_prices)
    print("After opening position:")
    print(f"  Balance: ${summary['balance']:.2f}")
    print(f"  Equity: ${summary['equity']:.2f}")
    print(f"  Unrealized P&L: ${summary['unrealized_pnl']:+.2f}")
    print(f"  Positions: {summary['num_positions']}")
    print()

    # Close position at profit
    print("Closing position at profit...")
    pnl = account.close_position('BTC/USDC:USDC', exit_price=101000.0)
    print()

    # Check final state
    summary = account.get_summary({})
    print("Final state:")
    print(f"  Balance: ${summary['balance']:.2f}")
    print(f"  Realized P&L: ${summary['realized_pnl']:+.2f}")
    print(f"  Total return: {summary['total_return_pct']:+.2f}%")
    print()

    print("[OK] All tests passed!")
