"""
Market data fetching from Hyperliquid via ccxt.

This module provides the MarketDataFetcher class for:
- Fetching current ticker data (price, volume, etc.)
- Fetching OHLCV (candlestick) data for technical analysis
- Handling API errors gracefully
- Returning data as pandas DataFrames
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import ccxt
import pandas as pd
import logging

from config.settings import settings


logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetch market data from Hyperliquid exchange via ccxt."""

    def __init__(self):
        """
        Initialize exchange connection.

        Uses Hyperliquid exchange from ccxt with API credentials if available.
        Enables rate limiting to avoid exceeding API limits.
        """
        try:
            # No authentication needed for public market data
            exchange_config = {
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",  # Hyperliquid perpetuals (swaps)
                    # Skip HIP-3 spot markets since we're only trading perps
                    # This avoids the "Too many DEXes" error during market loading
                    "fetchMarkets": {
                        "types": ["swap"],  # Only load perpetual markets
                        "hip3": False  # Disable HIP-3 spot market aggregation
                    }
                }
            }

            self.exchange = ccxt.hyperliquid(exchange_config)

            if settings.hyperliquid_testnet:
                self.exchange.set_sandbox_mode(True)

            logger.info(f"Initialized Hyperliquid exchange connection (testnet={settings.hyperliquid_testnet})")

        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise

    def _to_ccxt_symbol(self, symbol: str) -> str:
        """Convert simple symbol (BTC) to CCXT Hyperliquid format (BTC/USDC:USDC)."""
        # If it already looks like a CCXT symbol, leave it alone
        if "/" in symbol and ":" in symbol:
            return symbol
        # Otherwise append the standard suffix
        return f"{symbol}/USDC:USDC"

    def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Fetch current ticker data for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')

        Returns:
            Dictionary with ticker data or None if error
        """
        try:
            ccxt_symbol = self._to_ccxt_symbol(symbol)
            ticker = self.exchange.fetch_ticker(ccxt_symbol)

            # Handle None timestamp from Hyperliquid
            timestamp_ms = ticker.get("timestamp")
            if timestamp_ms is None:
                timestamp = datetime.now()
            else:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            return {
                "symbol": symbol,
                "price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume": ticker.get("quoteVolume"),
                "timestamp": timestamp,
            }

        except ccxt.ExchangeNotAvailable as e:
            logger.warning(f"Exchange not available for {symbol}: {e}")
            return None
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded fetching {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "3m",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')
            timeframe: Candlestick interval ('1m', '3m', '5m', '15m', '1h', '4h', etc.)
            limit: Number of candles to fetch (max depends on exchange)

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Empty DataFrame if error occurs
        """
        try:
            ccxt_symbol = self._to_ccxt_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)

            if not ohlcv:
                logger.warning(f"No OHLCV data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            # Create DataFrame with proper column names
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

            # Convert timestamp from milliseconds to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            # Ensure numeric types
            df["open"] = pd.to_numeric(df["open"])
            df["high"] = pd.to_numeric(df["high"])
            df["low"] = pd.to_numeric(df["low"])
            df["close"] = pd.to_numeric(df["close"])
            df["volume"] = pd.to_numeric(df["volume"])

            return df

        except ccxt.ExchangeNotAvailable as e:
            logger.warning(f"Exchange not available for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded fetching {symbol} {timeframe}: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            return pd.DataFrame()

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Fetch current funding rate for a perpetual.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')

        Returns:
            Funding rate as float or None if error
        """
        try:
            ccxt_symbol = self._to_ccxt_symbol(symbol)
            ticker = self.exchange.fetch_ticker(ccxt_symbol)
            return ticker.get("info", {}).get("fundingRate")
        except Exception as e:
            logger.debug(f"Error fetching funding rate for {symbol}: {e}")
            return None

    def fetch_open_interest(self, symbol: str) -> Optional[float]:
        """
        Fetch open interest for a perpetual.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')

        Returns:
            Open interest or None if error
        """
        try:
            ccxt_symbol = self._to_ccxt_symbol(symbol)
            ticker = self.exchange.fetch_ticker(ccxt_symbol)
            # OpenInterest might be in different locations depending on exchange response
            return ticker.get("info", {}).get("openInterest")
        except Exception as e:
            logger.debug(f"Error fetching open interest for {symbol}: {e}")
            return None

    def fetch_all_tickers(self) -> Dict[str, Optional[Dict]]:
        """
        Fetch tickers for all configured trading assets.

        Returns:
            Dictionary mapping symbol to ticker data
        """
        tickers = {}
        assets = settings.get_trading_assets()

        for symbol in assets:
            ticker = self.fetch_ticker(symbol)
            tickers[symbol] = ticker

        return tickers

    def fetch_market_data_bundle(
        self,
        symbol: str,
        timeframe: str = "3m",
        limit: int = 100
    ) -> Dict:
        """
        Fetch complete market data bundle for a symbol.

        Combines ticker, OHLCV, funding rate, and open interest.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')
            timeframe: Candlestick interval
            limit: Number of candles

        Returns:
            Dictionary with all market data
        """
        bundle = {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "ticker": self.fetch_ticker(symbol),
            "ohlcv": self.fetch_ohlcv(symbol, timeframe, limit),
            "funding_rate": self.fetch_funding_rate(symbol),
            "open_interest": self.fetch_open_interest(symbol),
        }

        return bundle


def get_market_data_fetcher() -> MarketDataFetcher:
    """Get or create market data fetcher instance."""
    return MarketDataFetcher()


if __name__ == "__main__":
    """Test the market data fetcher."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 70)
    print("Market Data Fetcher Test")
    print("=" * 70)
    print()

    try:
        fetcher = get_market_data_fetcher()

        # Test 1: Fetch single ticker
        print("Test 1: Fetching BTC ticker...")
        btc_ticker = fetcher.fetch_ticker("BTC")
        if btc_ticker:
            print(f"  BTC Price: ${btc_ticker['price']:,.2f}")
            print(f"  Bid: ${btc_ticker['bid']:,.2f} | Ask: ${btc_ticker['ask']:,.2f}")
            print(f"  Volume: {btc_ticker['volume']:,.0f}")
            print(f"  Timestamp: {btc_ticker['timestamp']}")
        else:
            print("  Failed to fetch BTC ticker")
        print()

        # Test 2: Fetch OHLCV data
        print("Test 2: Fetching BTC 3-minute OHLCV (last 10 candles)...")
        btc_ohlcv = fetcher.fetch_ohlcv("BTC", timeframe="3m", limit=10)
        if not btc_ohlcv.empty:
            print(f"  Retrieved {len(btc_ohlcv)} candles")
            print("\n  Last 3 candles:")
            print(btc_ohlcv.tail(3).to_string(index=False))
        else:
            print("  Failed to fetch OHLCV data")
        print()

        # Test 3: Fetch all configured assets
        print("Test 3: Fetching all configured assets...")
        all_tickers = fetcher.fetch_all_tickers()
        for symbol, ticker in all_tickers.items():
            if ticker:
                print(f"  {symbol}: ${ticker['price']:,.2f}")
            else:
                print(f"  {symbol}: [Failed to fetch]")
        print()

        # Test 4: Fetch market data bundle
        print("Test 4: Fetching complete market data bundle for ETH...")
        eth_bundle = fetcher.fetch_market_data_bundle("ETH")
        if eth_bundle["ticker"]:
            print(f"  ETH Price: ${eth_bundle['ticker']['price']:,.2f}")
            print(f"  Funding Rate: {eth_bundle['funding_rate']}")
            print(f"  Open Interest: {eth_bundle['open_interest']}")
            print(f"  OHLCV candles: {len(eth_bundle['ohlcv'])}")
        else:
            print("  Failed to fetch ETH market data")
        print()

        print("=" * 70)
        print("All tests completed!")
        print("=" * 70)

    except Exception as e:
        print(f"Error during testing: {e}")
        logger.exception("Test failed")
