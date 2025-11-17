"""
Hyperliquid order execution for live trading.

This module handles real order placement on Hyperliquid exchange.
Supports both testnet and mainnet trading.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from config.settings import settings


logger = logging.getLogger(__name__)


class HyperliquidExecutor:
    """
    Execute trades on Hyperliquid exchange.

    Handles order placement, position management, and leverage settings
    for both testnet and mainnet environments.
    """

    def __init__(self, testnet: bool = True):
        """
        Initialize Hyperliquid executor.

        Args:
            testnet: If True, use testnet. If False, use mainnet.
        """
        self.testnet = testnet
        self.base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL

        # Initialize wallet account from private key
        if not settings.hyperliquid_wallet_private_key:
            raise ValueError("HYPERLIQUID_WALLET_PRIVATE_KEY not configured in .env")

        self.account: LocalAccount = eth_account.Account.from_key(
            settings.hyperliquid_wallet_private_key
        )

        # Use account_address if provided, otherwise derive from private key
        self.address = settings.hyperliquid_account_address or self.account.address

        logger.info(f"Hyperliquid Executor initialized")
        logger.info(f"  Mode: {'TESTNET' if testnet else 'MAINNET'}")
        logger.info(f"  Account: {self.address}")
        if self.address != self.account.address:
            logger.info(f"  Agent wallet: {self.account.address}")

        # Initialize Info and Exchange clients
        self.info = Info(self.base_url, skip_ws=True)
        self.exchange = Exchange(
            self.account,
            self.base_url,
            account_address=self.address if self.address != self.account.address else None
        )

        # Verify account has balance
        self._verify_account()

    def _verify_account(self):
        """Verify account exists and has balance."""
        try:
            user_state = self.info.user_state(self.address)
            margin_summary = user_state["marginSummary"]
            account_value = float(margin_summary["accountValue"])

            if account_value == 0:
                logger.warning(f"Account {self.address} has zero balance!")
                logger.warning(f"Make sure to fund your account on {self.base_url}")
            else:
                logger.info(f"Account value: ${account_value:,.2f}")
        except Exception as e:
            logger.error(f"Failed to verify account: {e}")
            raise

    def get_account_state(self) -> Dict[str, Any]:
        """
        Get current account state from Hyperliquid.

        Returns:
            Dict with account_value, margin_used, positions, etc.
        """
        try:
            user_state = self.info.user_state(self.address)
            margin_summary = user_state["marginSummary"]

            return {
                "account_value": float(margin_summary["accountValue"]),
                "total_margin_used": float(margin_summary["totalMarginUsed"]),
                "total_ntl_pos": float(margin_summary["totalNtlPos"]),
                "total_raw_usd": float(margin_summary["totalRawUsd"]),
                "positions": user_state.get("assetPositions", [])
            }
        except Exception as e:
            logger.error(f"Failed to get account state: {e}")
            return {}

    def set_leverage(self, coin: str, leverage: int, is_cross: bool = True) -> bool:
        """
        Set leverage for a specific coin.

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")
            leverage: Leverage multiplier (1-50 depending on coin)
            is_cross: If True, use cross margin. If False, use isolated margin.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove /USD:USD or /USDC:USDC suffix if present
            coin_clean = coin.split("/")[0] if "/" in coin else coin

            logger.info(f"Setting {coin_clean} leverage to {leverage}x ({'cross' if is_cross else 'isolated'})")

            result = self.exchange.update_leverage(leverage, coin_clean, is_cross)

            if result.get("status") == "ok":
                logger.info(f"Leverage set successfully for {coin_clean}")
                return True
            else:
                logger.error(f"Failed to set leverage: {result}")
                return False

        except Exception as e:
            logger.error(f"Error setting leverage for {coin}: {e}")
            return False

    def get_size_decimals(self, coin: str) -> int:
        """
        Get the size decimals (precision) for a coin from Hyperliquid metadata.

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")

        Returns:
            Number of decimal places allowed (default 8 if not found)
        """
        try:
            coin_clean = coin.split("/")[0] if "/" in coin else coin
            meta = self.info.meta()
            for asset in meta.get('universe', []):
                if asset.get('name') == coin_clean:
                    return asset.get('szDecimals', 8)
            return 8  # Default if not found
        except Exception as e:
            logger.warning(f"Failed to get size decimals for {coin}: {e}")
            return 8  # Default

    def usd_to_coin_size(self, coin: str, usd_amount: float, coin_price: float, leverage: float = 1.0) -> float:
        """
        Convert USD amount to coin size for order placement, properly rounded.

        Args:
            coin: Coin symbol (e.g., "BTC/USDC:USDC")
            usd_amount: Amount in USD to trade
            coin_price: Current price of the coin
            leverage: Leverage multiplier (position size = usd * leverage)

        Returns:
            Size in coins, rounded to correct precision

        Example:
            >>> executor.usd_to_coin_size("BTC", 50, 100000, 2)
            0.001  # $50 with 2x leverage = $100 position / $100k price = 0.001 BTC
        """
        # With leverage: position_size_usd = usd_amount * leverage
        # coin_size = position_size_usd / coin_price
        position_size_usd = usd_amount * leverage
        coin_size = position_size_usd / coin_price

        # Round to correct precision for this asset
        decimals = self.get_size_decimals(coin)
        coin_size_rounded = round(coin_size, decimals)

        return coin_size_rounded

    def market_open_usd(
        self,
        coin: str,
        is_buy: bool,
        usd_amount: float,
        current_price: float,
        leverage: int,
        slippage: float = 0.05
    ) -> Optional[Dict[str, Any]]:
        """
        Open a market position using USD amount (convenience wrapper).

        Args:
            coin: Coin symbol (e.g., "BTC/USD:USD")
            is_buy: True for long, False for short
            usd_amount: Margin amount in USD (e.g., $50)
            current_price: Current coin price
            leverage: Leverage multiplier (e.g., 2)
            slippage: Acceptable slippage (default 5%)

        Returns:
            Order result dict if successful, None otherwise
        """
        # Convert USD to coin size (with proper rounding)
        size = self.usd_to_coin_size(coin, usd_amount, current_price, leverage)
        notional = size * current_price
        logger.info(f"Position size: {size} {coin.split('/')[0] if '/' in coin else coin} (${notional:.2f} notional)")

        # Place order
        return self.market_open(coin, is_buy, size, leverage, slippage)

    def market_open(
        self,
        coin: str,
        is_buy: bool,
        size: float,
        leverage: Optional[int] = None,
        slippage: float = 0.05
    ) -> Optional[Dict[str, Any]]:
        """
        Open a market position.

        Args:
            coin: Coin symbol (e.g., "BTC/USD:USD")
            is_buy: True for long, False for short
            size: Position size in coins (not USD)
            leverage: Optional leverage to set before order (1-50)
            slippage: Acceptable slippage (default 5%)

        Returns:
            Order result dict if successful, None otherwise
        """
        try:
            # Clean coin symbol
            coin_clean = coin.split("/")[0] if "/" in coin else coin

            # Set leverage if provided
            if leverage:
                if not self.set_leverage(coin_clean, leverage):
                    logger.error("Failed to set leverage, aborting order")
                    return None

            logger.info(f"Market {'BUY' if is_buy else 'SELL'} {size} {coin_clean} @ {slippage*100}% slippage")

            # Place market order
            result = self.exchange.market_open(coin_clean, is_buy, size, None, slippage)

            if result.get("status") == "ok":
                logger.info(f"Market order placed successfully")

                # Parse fill information
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        logger.info(f"  Order #{filled['oid']} filled {filled['totalSz']} @ ${filled['avgPx']}")
                    elif "error" in status:
                        logger.error(f"  Order error: {status['error']}")

                return result
            else:
                logger.error(f"Market order failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Error placing market order for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def market_close(self, coin: str) -> Optional[Dict[str, Any]]:
        """
        Close all positions for a specific coin using market order.

        Args:
            coin: Coin symbol (e.g., "BTC/USD:USD")

        Returns:
            Order result dict if successful, None otherwise
        """
        try:
            # Clean coin symbol
            coin_clean = coin.split("/")[0] if "/" in coin else coin

            logger.info(f"Market CLOSE all {coin_clean} positions")

            # Close position
            result = self.exchange.market_close(coin_clean)

            if result.get("status") == "ok":
                logger.info(f"Position closed successfully")

                # Parse fill information
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        logger.info(f"  Order #{filled['oid']} filled {filled['totalSz']} @ ${filled['avgPx']}")
                    elif "error" in status:
                        logger.error(f"  Close error: {status['error']}")

                return result
            else:
                logger.error(f"Market close failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Error closing position for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders across all coins.

        Returns:
            True if all cancellations successful, False otherwise
        """
        try:
            open_orders = self.info.open_orders(self.address)

            if not open_orders:
                logger.info("No open orders to cancel")
                return True

            logger.info(f"Cancelling {len(open_orders)} open orders")

            success = True
            for order in open_orders:
                try:
                    coin = order["coin"]
                    oid = order["oid"]
                    logger.info(f"  Cancelling order {oid} for {coin}")
                    self.exchange.cancel(coin, oid)
                except Exception as e:
                    logger.error(f"  Failed to cancel order {oid}: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return False

    def close_all_positions(self) -> bool:
        """
        Emergency function: Close all open positions immediately.

        Returns:
            True if all positions closed, False otherwise
        """
        try:
            user_state = self.info.user_state(self.address)
            asset_positions = user_state.get("assetPositions", [])

            if not asset_positions:
                logger.info("No open positions to close")
                return True

            logger.warning(f"EMERGENCY: Closing all {len(asset_positions)} positions")

            success = True
            for asset_pos in asset_positions:
                try:
                    coin = asset_pos["position"]["coin"]
                    size = float(asset_pos["position"]["szi"])

                    if abs(size) > 0:  # Position exists
                        logger.warning(f"  Closing {coin} position (size: {size})")
                        result = self.market_close(coin)
                        if not result:
                            success = False
                except Exception as e:
                    logger.error(f"  Failed to close {coin}: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return False

    def get_position_info(self, coin: str) -> Optional[Dict[str, Any]]:
        """
        Get current position information for a specific coin.

        Args:
            coin: Coin symbol (e.g., "BTC/USD:USD")

        Returns:
            Position dict or None if no position
        """
        try:
            coin_clean = coin.split("/")[0] if "/" in coin else coin

            user_state = self.info.user_state(self.address)
            asset_positions = user_state.get("assetPositions", [])

            for asset_pos in asset_positions:
                if asset_pos["position"]["coin"] == coin_clean:
                    position = asset_pos["position"]
                    return {
                        "coin": position["coin"],
                        "size": float(position["szi"]),
                        "entry_price": float(position["entryPx"]),
                        "leverage": position["leverage"],
                        "unrealized_pnl": float(position["unrealizedPnl"]),
                        "liquidation_px": float(position["liquidationPx"]) if position.get("liquidationPx") else None,
                        "margin_used": float(position["marginUsed"])
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting position info for {coin}: {e}")
            return None


# Convenience function for getting executor instance
def get_executor(testnet: Optional[bool] = None) -> HyperliquidExecutor:
    """
    Get HyperliquidExecutor instance.

    Args:
        testnet: Override testnet setting from config. If None, use settings.hyperliquid_testnet

    Returns:
        Configured HyperliquidExecutor instance
    """
    use_testnet = testnet if testnet is not None else settings.hyperliquid_testnet
    return HyperliquidExecutor(testnet=use_testnet)


if __name__ == "__main__":
    # Test the executor
    print("=" * 70)
    print("HYPERLIQUID EXECUTOR TEST")
    print("=" * 70)

    try:
        executor = get_executor(testnet=True)

        print("\n[1/3] Getting account state...")
        account_state = executor.get_account_state()
        print(f"  Account Value: ${account_state['account_value']:,.2f}")
        print(f"  Margin Used: ${account_state['total_margin_used']:,.2f}")
        print(f"  Open Positions: {len(account_state['positions'])}")

        print("\n[2/3] Checking BTC position...")
        btc_position = executor.get_position_info("BTC")
        if btc_position:
            print(f"  BTC Position Size: {btc_position['size']}")
            print(f"  Entry Price: ${btc_position['entry_price']:,.2f}")
            print(f"  Unrealized PnL: ${btc_position['unrealized_pnl']:,.2f}")
        else:
            print("  No BTC position open")

        print("\n[3/3] Test complete!")
        print("\n[OK] Hyperliquid executor working correctly")

    except Exception as e:
        print(f"\n[ERROR] Executor test failed: {e}")
        import traceback
        traceback.print_exc()
