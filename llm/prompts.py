"""
Prompt templates for LLM trading decisions.

This module provides prompt generation for Claude to analyze market data
and make trading decisions. Based on Alpha Arena's proven methodology.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import json

import pandas as pd


class PromptBuilder:
    """Build prompts for LLM trading decisions."""

    SYSTEM_PROMPT = """You are an autonomous cryptocurrency trading agent operating on Hyperliquid exchange.

Your goal is to maximize profit and loss (PnL) while managing risk appropriately. You have been given real capital to trade and your performance will be measured by both absolute returns and risk-adjusted returns (Sharpe ratio).

## Your Capabilities
- Analyze technical indicators (EMA, RSI, MACD, ATR) across multiple timeframes
- Open long or short positions with leverage on perpetual futures
- Set profit targets, stop losses, and invalidation conditions
- Manage multiple positions across different cryptocurrencies

## Trading Rules
1. ALWAYS follow position sizing limits (max position size, max leverage)
2. NEVER exceed daily loss limits
3. Set clear exit plans for every position (profit target, stop loss, invalidation)
4. Be explicit about confidence levels (0.0 to 1.0)
5. Provide clear justification for every decision
6. Consider market context: funding rates, open interest, volume

## Risk Management
- Higher leverage = higher risk = should have tighter stops
- Consider liquidation prices when sizing positions
- Monitor Sharpe ratio to maintain risk-adjusted performance
- Respect daily loss limits to preserve capital

## Output Format
Return valid JSON with these exact fields:
{
    "coin": "BTC/USD:USD",
    "signal": "buy_to_enter|sell_to_enter|hold|close",
    "quantity_usd": 50.0,
    "leverage": 2.0,
    "confidence": 0.75,
    "exit_plan": {
        "profit_target": 111000.0,
        "stop_loss": 106361.0,
        "invalidation_condition": "4H RSI breaks below 40"
    },
    "justification": "Clear technical analysis reasoning"
}

IMPORTANT: Data is ordered OLDEST → NEWEST in all series."""

    @staticmethod
    def format_market_data(
        symbol: str,
        current_price: float,
        ohlcv_df: pd.DataFrame,
        indicators_df: pd.DataFrame,
        funding_rate: Optional[float] = None,
        open_interest: Optional[float] = None,
    ) -> str:
        """
        Format market data for a single asset.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')
            current_price: Current market price
            ohlcv_df: OHLCV data with indicators
            indicators_df: DataFrame with calculated indicators
            funding_rate: Perpetual funding rate
            open_interest: Current open interest

        Returns:
            Formatted market data string
        """
        lines = []
        lines.append(f"### {symbol} DATA")
        lines.append("")

        # Current state
        latest = indicators_df.iloc[-1] if not indicators_df.empty else {}

        current_ema20 = latest.get('ema_20', 'N/A')
        current_macd = latest.get('macd', 'N/A')
        current_rsi_7 = latest.get('rsi_7', 'N/A')

        lines.append(f"current_price = {current_price:.2f}, "
                    f"current_ema20 = {current_ema20}, "
                    f"current_macd = {current_macd}, "
                    f"current_rsi (7 period) = {current_rsi_7}")
        lines.append("")

        # Funding rate and open interest
        if funding_rate is not None or open_interest is not None:
            lines.append(f"Open Interest & Funding Rate:")
            if open_interest is not None:
                # Calculate average open interest (use recent data or just current)
                lines.append(f"Open Interest: Latest: {open_interest:.2f}")
            if funding_rate is not None:
                lines.append(f"Funding Rate: {funding_rate}")
            lines.append("")

        # Intraday series (3-minute or short timeframe)
        lines.append("**Intraday series (3-minute intervals, oldest → latest):**")
        lines.append("")

        if not indicators_df.empty and len(indicators_df) >= 10:
            last_10 = indicators_df.tail(10)

            # Prices
            if 'close' in last_10.columns:
                prices = last_10['close'].tolist()
                lines.append(f"Mid prices: {[round(p, 2) for p in prices]}")
                lines.append("")

            # EMA 20
            if 'ema_20' in last_10.columns:
                ema_20 = last_10['ema_20'].dropna().tolist()
                if ema_20:
                    lines.append(f"EMA indicators (20-period): {[round(e, 2) for e in ema_20]}")
                    lines.append("")

            # MACD
            if 'macd' in last_10.columns:
                macd = last_10['macd'].dropna().tolist()
                if macd:
                    lines.append(f"MACD indicators: {[round(m, 3) for m in macd]}")
                    lines.append("")

            # RSI 7 and 14
            if 'rsi_7' in last_10.columns:
                rsi_7 = last_10['rsi_7'].dropna().tolist()
                if rsi_7:
                    lines.append(f"RSI indicators (7-Period): {[round(r, 3) for r in rsi_7]}")
                    lines.append("")

            if 'rsi_14' in last_10.columns:
                rsi_14 = last_10['rsi_14'].dropna().tolist()
                if rsi_14:
                    lines.append(f"RSI indicators (14-Period): {[round(r, 3) for r in rsi_14]}")
                    lines.append("")

        # Longer-term context (4-hour timeframe) - if available
        lines.append("**Longer-term context (4-hour timeframe):**")
        lines.append("")

        if not indicators_df.empty:
            latest = indicators_df.iloc[-1]

            if 'ema_20' in latest and 'ema_50' in latest:
                lines.append(f"20-Period EMA: {latest['ema_20']:.2f} vs. 50-Period EMA: {latest['ema_50']:.2f}")
                lines.append("")

            if 'atr_3' in latest and 'atr_14' in latest:
                lines.append(f"3-Period ATR: {latest['atr_3']:.2f} vs. 14-Period ATR: {latest['atr_14']:.2f}")
                lines.append("")

            if 'volume' in latest and 'volume_sma_20' in latest:
                lines.append(f"Current Volume: {latest['volume']:.2f} vs. Average Volume: {latest['volume_sma_20']:.2f}")
                lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_account_state(
        available_cash: float,
        total_value: float,
        positions: List[Dict[str, Any]],
        total_return_pct: float,
        sharpe_ratio: float,
    ) -> str:
        """
        Format current account state.

        Args:
            available_cash: Available cash for trading
            total_value: Total account value
            positions: List of open positions
            total_return_pct: Total return percentage
            sharpe_ratio: Current Sharpe ratio

        Returns:
            Formatted account state string
        """
        lines = []
        lines.append("### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE")
        lines.append("")
        lines.append(f"Current Total Return (percent): {total_return_pct:.2f}%")
        lines.append("")
        lines.append(f"Available Cash: {available_cash:.2f}")
        lines.append("")
        lines.append(f"**Current Account Value:** {total_value:.2f}")
        lines.append("")

        if positions:
            lines.append("Current live positions & performance:")
            for pos in positions:
                lines.append(str(pos))
            lines.append("")
        else:
            lines.append("Current live positions: None")
            lines.append("")

        lines.append(f"Sharpe Ratio: {sharpe_ratio:.3f}")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def build_trading_prompt(
        market_data: Dict[str, Dict],
        account_state: Dict[str, Any],
        minutes_since_start: int = 0,
    ) -> str:
        """
        Build complete trading prompt for LLM.

        Args:
            market_data: Dictionary mapping symbol to market data
            account_state: Account state information
            minutes_since_start: Minutes since trading started

        Returns:
            Complete prompt string
        """
        lines = []

        # Header
        lines.append(f"It has been {minutes_since_start} minutes since you started trading.")
        lines.append("")
        lines.append("Below, we are providing you with a variety of state data, price data, "
                    "and predictive signals so you can discover alpha. Below that is your current "
                    "account information, value, performance, positions, etc.")
        lines.append("")
        lines.append("**ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST**")
        lines.append("")
        lines.append("**Timeframes note:** Unless stated otherwise in a section title, intraday series "
                    "are provided at **3-minute intervals**. If a coin uses a different interval, "
                    "it is explicitly stated in that coin's section.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Current market state
        lines.append("### CURRENT MARKET STATE FOR ALL COINS")
        lines.append("")

        # Add market data for each asset
        for symbol, data in market_data.items():
            market_section = PromptBuilder.format_market_data(
                symbol=symbol,
                current_price=data.get('current_price', 0),
                ohlcv_df=data.get('ohlcv', pd.DataFrame()),
                indicators_df=data.get('indicators', pd.DataFrame()),
                funding_rate=data.get('funding_rate'),
                open_interest=data.get('open_interest'),
            )
            lines.append(market_section)

        # Account state
        account_section = PromptBuilder.format_account_state(
            available_cash=account_state.get('available_cash', 0),
            total_value=account_state.get('total_value', 0),
            positions=account_state.get('positions', []),
            total_return_pct=account_state.get('total_return_pct', 0),
            sharpe_ratio=account_state.get('sharpe_ratio', 0),
        )
        lines.append(account_section)

        lines.append("---")
        lines.append("")
        lines.append("Based on this data, make your trading decision. Return valid JSON only.")

        return "\n".join(lines)


def get_system_prompt() -> str:
    """Get the system prompt for Claude."""
    return PromptBuilder.SYSTEM_PROMPT


def build_user_prompt(
    market_data: Dict[str, Dict],
    account_state: Dict[str, Any],
    minutes_since_start: int = 0,
) -> str:
    """
    Build user prompt for trading decision.

    Args:
        market_data: Market data for all assets
        account_state: Current account state
        minutes_since_start: Minutes since trading started

    Returns:
        Formatted prompt string
    """
    return PromptBuilder.build_trading_prompt(
        market_data=market_data,
        account_state=account_state,
        minutes_since_start=minutes_since_start,
    )


if __name__ == "__main__":
    """Test prompt generation."""

    print("=" * 70)
    print("Prompt Builder Test")
    print("=" * 70)
    print()

    # Create sample market data
    import numpy as np

    sample_ohlcv = pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=100, freq='3min'),
        'open': np.random.uniform(50000, 51000, 100),
        'high': np.random.uniform(50500, 51500, 100),
        'low': np.random.uniform(49500, 50500, 100),
        'close': np.random.uniform(50000, 51000, 100),
        'volume': np.random.uniform(1000, 10000, 100),
        'ema_20': np.random.uniform(50000, 51000, 100),
        'ema_50': np.random.uniform(49500, 50500, 100),
        'rsi_7': np.random.uniform(30, 70, 100),
        'rsi_14': np.random.uniform(30, 70, 100),
        'macd': np.random.uniform(-100, 100, 100),
        'atr_3': np.random.uniform(200, 400, 100),
        'atr_14': np.random.uniform(300, 500, 100),
        'volume_sma_20': np.random.uniform(5000, 7000, 100),
    })

    market_data = {
        'BTC/USD:USD': {
            'current_price': 50500.0,
            'ohlcv': sample_ohlcv,
            'indicators': sample_ohlcv,
            'funding_rate': 0.0001,
            'open_interest': 25000.0,
        },
        'ETH/USD:USD': {
            'current_price': 3500.0,
            'ohlcv': sample_ohlcv * 0.07,  # Scale for ETH
            'indicators': sample_ohlcv * 0.07,
            'funding_rate': 0.00008,
            'open_interest': 15000.0,
        },
    }

    account_state = {
        'available_cash': 8500.0,
        'total_value': 10250.0,
        'total_return_pct': 2.5,
        'sharpe_ratio': 0.025,
        'positions': [
            {
                'symbol': 'BTC/USD:USD',
                'quantity': 0.1,
                'entry_price': 50000.0,
                'current_price': 50500.0,
                'unrealized_pnl': 50.0,
                'leverage': 2.0,
            }
        ],
    }

    # Build prompt
    print("Building trading prompt...")
    print()

    prompt = build_user_prompt(
        market_data=market_data,
        account_state=account_state,
        minutes_since_start=120,
    )

    print("=" * 70)
    print("GENERATED PROMPT:")
    print("=" * 70)
    print(prompt[:2000])  # Print first 2000 chars
    print()
    print(f"... (total length: {len(prompt)} characters)")
    print()
    print("=" * 70)
    print("System prompt length:", len(get_system_prompt()))
    print("User prompt length:", len(prompt))
    print("=" * 70)
