"""
Calculate technical indicators for market data.

This module provides technical indicator calculations using pandas_ta.
Supports both intraday (3-minute) and longer-term (4-hour) timeframes
matching the Alpha Arena methodology.
"""

from typing import Optional, Dict, List

import pandas as pd
import pandas_ta as ta
import logging


logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for trading analysis."""

    # Indicator periods (from Alpha Arena)
    EMA_SHORT = 20
    EMA_LONG = 50
    RSI_SHORT = 7
    RSI_LONG = 14
    ATR_SHORT = 3
    ATR_LONG = 14

    @staticmethod
    def calculate_ema(
        df: pd.DataFrame,
        period: int = 20,
        column: str = "close"
    ) -> Optional[pd.Series]:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            df: DataFrame with OHLCV data
            period: EMA period (default 20)
            column: Column to calculate on (default 'close')

        Returns:
            Series with EMA values or None if error
        """
        try:
            if column not in df.columns:
                logger.warning(f"Column '{column}' not found in DataFrame")
                return None

            if len(df) < period:
                logger.debug(f"Not enough data for EMA{period} (need {period}, have {len(df)})")
                return None

            return ta.ema(df[column], length=period)

        except Exception as e:
            logger.error(f"Error calculating EMA{period}: {e}")
            return None

    @staticmethod
    def calculate_rsi(
        df: pd.DataFrame,
        period: int = 14,
        column: str = "close"
    ) -> Optional[pd.Series]:
        """
        Calculate Relative Strength Index (RSI).

        RSI ranges from 0-100:
        - < 30: Oversold
        - > 70: Overbought
        - 50: Neutral

        Args:
            df: DataFrame with OHLCV data
            period: RSI period (default 14)
            column: Column to calculate on (default 'close')

        Returns:
            Series with RSI values or None if error
        """
        try:
            if column not in df.columns:
                logger.warning(f"Column '{column}' not found in DataFrame")
                return None

            if len(df) < period + 1:
                logger.debug(f"Not enough data for RSI{period} (need {period + 1}, have {len(df)})")
                return None

            return ta.rsi(df[column], length=period)

        except Exception as e:
            logger.error(f"Error calculating RSI{period}: {e}")
            return None

    @staticmethod
    def calculate_macd(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        column: str = "close"
    ) -> Optional[pd.DataFrame]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Returns DataFrame with:
        - MACD line
        - Signal line
        - Histogram (difference between MACD and signal)

        Args:
            df: DataFrame with OHLCV data
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)
            column: Column to calculate on (default 'close')

        Returns:
            DataFrame with MACD components or None if error
        """
        try:
            if column not in df.columns:
                logger.warning(f"Column '{column}' not found in DataFrame")
                return None

            if len(df) < slow + signal - 1:
                logger.debug(f"Not enough data for MACD (need {slow + signal - 1}, have {len(df)})")
                return None

            return ta.macd(df[column], fast=fast, slow=slow, signal=signal)

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    @staticmethod
    def calculate_atr(
        df: pd.DataFrame,
        period: int = 14
    ) -> Optional[pd.Series]:
        """
        Calculate Average True Range (ATR).

        ATR measures volatility. Larger ATR = higher volatility.

        Args:
            df: DataFrame with high, low, close columns
            period: ATR period (default 14)

        Returns:
            Series with ATR values or None if error
        """
        try:
            required_cols = ["high", "low", "close"]
            if not all(col in df.columns for col in required_cols):
                logger.warning(f"Missing required columns for ATR: {required_cols}")
                return None

            if len(df) < period + 1:
                logger.debug(f"Not enough data for ATR{period} (need {period + 1}, have {len(df)})")
                return None

            return ta.atr(df["high"], df["low"], df["close"], length=period)

        except Exception as e:
            logger.error(f"Error calculating ATR{period}: {e}")
            return None

    @staticmethod
    def calculate_sma(
        df: pd.DataFrame,
        period: int = 20,
        column: str = "volume"
    ) -> Optional[pd.Series]:
        """
        Calculate Simple Moving Average (SMA).

        Often used for volume analysis.

        Args:
            df: DataFrame with data
            period: SMA period (default 20)
            column: Column to calculate on (default 'volume')

        Returns:
            Series with SMA values or None if error
        """
        try:
            if column not in df.columns:
                logger.warning(f"Column '{column}' not found in DataFrame")
                return None

            if len(df) < period:
                logger.debug(f"Not enough data for SMA{period} (need {period}, have {len(df)})")
                return None

            return ta.sma(df[column], length=period)

        except Exception as e:
            logger.error(f"Error calculating SMA{period}: {e}")
            return None

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators and add to DataFrame.

        Adds the following columns to input DataFrame:
        - ema_20, ema_50: Exponential Moving Averages
        - rsi_7, rsi_14: Relative Strength Index
        - macd, macd_signal, macd_hist: MACD components
        - atr_3, atr_14: Average True Range
        - volume_sma_20: 20-period volume SMA

        Args:
            df: DataFrame with OHLCV data (must have: open, high, low, close, volume)

        Returns:
            DataFrame with all indicators added
        """
        result_df = df.copy()

        try:
            # Validate input
            required_cols = ["open", "high", "low", "close", "volume"]
            if not all(col in result_df.columns for col in required_cols):
                missing = [col for col in required_cols if col not in result_df.columns]
                logger.error(f"Missing required columns: {missing}")
                return result_df

            if len(result_df) < 2:
                logger.warning("DataFrame too small for indicator calculation")
                return result_df

            # EMAs
            logger.debug(f"Calculating EMAs (have {len(result_df)} candles)")
            ema_20 = TechnicalIndicators.calculate_ema(result_df, period=20)
            if ema_20 is not None:
                result_df["ema_20"] = ema_20

            ema_50 = TechnicalIndicators.calculate_ema(result_df, period=50)
            if ema_50 is not None:
                result_df["ema_50"] = ema_50

            # RSIs
            logger.debug("Calculating RSIs")
            rsi_7 = TechnicalIndicators.calculate_rsi(result_df, period=7)
            if rsi_7 is not None:
                result_df["rsi_7"] = rsi_7

            rsi_14 = TechnicalIndicators.calculate_rsi(result_df, period=14)
            if rsi_14 is not None:
                result_df["rsi_14"] = rsi_14

            # MACD
            logger.debug("Calculating MACD")
            macd_df = TechnicalIndicators.calculate_macd(result_df)
            if macd_df is not None and not macd_df.empty:
                # pandas_ta returns columns like MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
                macd_cols = [col for col in macd_df.columns if "MACD" in col or "MACDs" in col or "MACDh" in col]
                if macd_cols:
                    for col in macd_df.columns:
                        if "MACD_12_26_9" in col:
                            result_df["macd"] = macd_df[col]
                        elif "MACDs_12_26_9" in col:
                            result_df["macd_signal"] = macd_df[col]
                        elif "MACDh_12_26_9" in col:
                            result_df["macd_hist"] = macd_df[col]

            # ATRs
            logger.debug("Calculating ATRs")
            atr_3 = TechnicalIndicators.calculate_atr(result_df, period=3)
            if atr_3 is not None:
                result_df["atr_3"] = atr_3

            atr_14 = TechnicalIndicators.calculate_atr(result_df, period=14)
            if atr_14 is not None:
                result_df["atr_14"] = atr_14

            # Volume SMA
            logger.debug("Calculating volume SMA")
            volume_sma = TechnicalIndicators.calculate_sma(result_df, period=20, column="volume")
            if volume_sma is not None:
                result_df["volume_sma_20"] = volume_sma

            return result_df

        except Exception as e:
            logger.error(f"Error calculating all indicators: {e}")
            return result_df


if __name__ == "__main__":
    """Test technical indicator calculations."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 70)
    print("Technical Indicators Test")
    print("=" * 70)
    print()

    # Create sample data
    import numpy as np
    from datetime import datetime, timedelta

    print("Creating sample OHLCV data...")
    now = datetime.now()
    timestamps = [now - timedelta(minutes=i*3) for i in range(100, -1, -1)]

    # Generate realistic price data (random walk)
    base_price = 50000
    returns = np.random.normal(0.0001, 0.005, 101)
    prices = base_price * np.exp(np.cumsum(returns))

    df_test = pd.DataFrame({
        "timestamp": timestamps,
        "open": prices * (1 + np.random.uniform(-0.002, 0.002, 101)),
        "high": prices * (1 + np.abs(np.random.uniform(0, 0.005, 101))),
        "low": prices * (1 - np.abs(np.random.uniform(0, 0.005, 101))),
        "close": prices,
        "volume": np.random.uniform(1000, 10000, 101),
    })

    print(f"Sample data shape: {df_test.shape}")
    print()

    # Test 1: Individual indicator calculations
    print("Test 1: Individual indicators")
    print("-" * 70)

    # EMA
    ema_20 = TechnicalIndicators.calculate_ema(df_test, period=20)
    if ema_20 is not None:
        print(f"EMA20 (latest): {ema_20.iloc[-1]:.2f}")

    # RSI
    rsi_14 = TechnicalIndicators.calculate_rsi(df_test, period=14)
    if rsi_14 is not None:
        print(f"RSI14 (latest): {rsi_14.iloc[-1]:.2f} {'(Overbought)' if rsi_14.iloc[-1] > 70 else '(Oversold)' if rsi_14.iloc[-1] < 30 else '(Neutral)'}")

    # MACD
    macd = TechnicalIndicators.calculate_macd(df_test)
    if macd is not None:
        print(f"MACD columns: {list(macd.columns)}")

    # ATR
    atr_14 = TechnicalIndicators.calculate_atr(df_test, period=14)
    if atr_14 is not None:
        print(f"ATR14 (latest): {atr_14.iloc[-1]:.2f}")

    print()

    # Test 2: Calculate all indicators
    print("Test 2: Calculate all indicators at once")
    print("-" * 70)

    df_with_indicators = TechnicalIndicators.calculate_all(df_test)

    # Show columns that were added
    new_cols = set(df_with_indicators.columns) - set(df_test.columns)
    print(f"Indicator columns added: {sorted(new_cols)}")
    print()

    # Show latest row
    print("Latest row with all indicators:")
    latest = df_with_indicators.iloc[-1]
    indicator_cols = sorted(new_cols)
    for col in indicator_cols:
        if col in latest.index:
            value = latest[col]
            if pd.notna(value):
                if isinstance(value, float):
                    print(f"  {col}: {value:.4f}")
                else:
                    print(f"  {col}: {value}")

    print()
    print("=" * 70)
    print("All indicator tests completed!")
    print("=" * 70)
