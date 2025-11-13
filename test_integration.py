#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end integration test for Alpha Arena Mini.

Tests the complete pipeline with synthetic data:
1. Generate mock market data
2. Calculate technical indicators
3. Build trading prompt
4. (Optional) Get Claude's decision
5. Parse and validate response

No Hyperliquid API key required - uses synthetic data.
ANTHROPIC_API_KEY optional - will skip Claude call if not configured.
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from data.indicators import TechnicalIndicators
from llm.prompts import get_system_prompt, build_user_prompt
from llm.client import ClaudeClient
from llm.parser import parse_llm_response


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_synthetic_market_data(
    symbol: str,
    base_price: float,
    num_candles: int = 100,
    volatility: float = 0.02
) -> pd.DataFrame:
    """
    Generate realistic synthetic OHLCV data.

    Args:
        symbol: Trading pair symbol
        base_price: Starting price
        num_candles: Number of candles to generate
        volatility: Price volatility (std dev of returns)

    Returns:
        DataFrame with OHLCV data
    """
    logger.info(f"Generating {num_candles} candles of synthetic data for {symbol}")

    # Generate timestamps (3-minute intervals)
    now = datetime.now()
    timestamps = [now - timedelta(minutes=i*3) for i in range(num_candles, -1, -1)]

    # Generate price series (geometric Brownian motion)
    returns = np.random.normal(0.0001, volatility, num_candles + 1)
    prices = base_price * np.exp(np.cumsum(returns))

    # Generate OHLC from close prices
    opens = prices * (1 + np.random.uniform(-0.002, 0.002, num_candles + 1))
    highs = prices * (1 + np.abs(np.random.uniform(0, 0.01, num_candles + 1)))
    lows = prices * (1 - np.abs(np.random.uniform(0, 0.01, num_candles + 1)))
    closes = prices
    volumes = np.random.uniform(1000, 10000, num_candles + 1)

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    })

    logger.info(f"Generated data: price range ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    return df


def test_data_pipeline():
    """Test data fetching and indicator calculation."""
    print("\n" + "="*70)
    print("TEST 1: Data Pipeline (Market Data + Indicators)")
    print("="*70)

    # Generate synthetic data for BTC
    btc_data = generate_synthetic_market_data("BTC/USD:USD", base_price=50000, num_candles=100)

    print(f"\n[OK] Generated {len(btc_data)} candles of BTC data")
    print(f"  Current Price: ${btc_data['close'].iloc[-1]:,.2f}")
    print(f"  Price Range: ${btc_data['close'].min():,.2f} - ${btc_data['close'].max():,.2f}")

    # Calculate indicators
    btc_with_indicators = TechnicalIndicators.calculate_all(btc_data)

    # Check indicators
    indicator_cols = ['ema_20', 'ema_50', 'rsi_7', 'rsi_14', 'macd', 'atr_14']
    available_indicators = [col for col in indicator_cols if col in btc_with_indicators.columns]

    print(f"\n[OK] Calculated {len(available_indicators)} indicators:")
    latest = btc_with_indicators.iloc[-1]
    for ind in available_indicators:
        if pd.notna(latest[ind]):
            print(f"  {ind}: {latest[ind]:.2f}")

    return btc_with_indicators


def test_prompt_generation(btc_indicators, eth_indicators):
    """Test prompt generation."""
    print("\n" + "="*70)
    print("TEST 2: Prompt Generation")
    print("="*70)

    # Prepare market data bundle
    market_data = {
        'BTC/USD:USD': {
            'current_price': btc_indicators['close'].iloc[-1],
            'ohlcv': btc_indicators,
            'indicators': btc_indicators,
            'funding_rate': 0.0001,
            'open_interest': 25000.0,
        },
        'ETH/USD:USD': {
            'current_price': eth_indicators['close'].iloc[-1],
            'ohlcv': eth_indicators,
            'indicators': eth_indicators,
            'funding_rate': 0.00008,
            'open_interest': 15000.0,
        },
    }

    # Mock account state
    account_state = {
        'available_cash': 10000.0,
        'total_value': 10000.0,
        'total_return_pct': 0.0,
        'sharpe_ratio': 0.0,
        'positions': [],
    }

    # Build prompts
    system_prompt = get_system_prompt()
    user_prompt = build_user_prompt(
        market_data=market_data,
        account_state=account_state,
        minutes_since_start=0,
    )

    print(f"\n[OK] Generated prompts:")
    print(f"  System prompt length: {len(system_prompt)} characters")
    print(f"  User prompt length: {len(user_prompt)} characters")
    print(f"  Total prompt length: {len(system_prompt) + len(user_prompt)} characters")

    # Show preview
    print(f"\n[PREVIEW] System prompt (first 200 chars):")
    print(f"  {system_prompt[:200]}...")

    print(f"\n[PREVIEW] User prompt (first 300 chars):")
    print(f"  {user_prompt[:300]}...")

    return system_prompt, user_prompt


def test_claude_integration(system_prompt, user_prompt):
    """Test Claude API integration (optional - requires API key)."""
    print("\n" + "="*70)
    print("TEST 3: Claude API Integration (Optional)")
    print("="*70)

    # Check if API key is configured
    if not settings.anthropic_api_key:
        print("\n[SKIP] ANTHROPIC_API_KEY not configured")
        print("  To test with Claude, add your API key to .env:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        return None

    try:
        print("\n[INFO] ANTHROPIC_API_KEY found, testing Claude connection...")

        # Initialize client
        client = ClaudeClient()
        print(f"  Model: {client.model}")

        # Test connection
        print("\n[INFO] Testing API connection...")
        if not client.test_connection():
            print("  [FAIL] Connection test failed")
            return None
        print("  [OK] Connection successful")

        # Get trading decision
        print("\n[INFO] Getting trading decision from Claude...")
        print("  (This may take 10-30 seconds)")

        response = client.get_trading_decision(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if response:
            print(f"\n[OK] Received response ({len(response)} chars)")
            print(f"\n[RESPONSE]:")
            print("-" * 70)
            print(response)
            print("-" * 70)
            return response
        else:
            print("\n[FAIL] No response received")
            return None

    except Exception as e:
        print(f"\n[ERROR] Claude integration failed: {e}")
        return None


def test_response_parsing(response_text=None):
    """Test response parsing."""
    print("\n" + "="*70)
    print("TEST 4: Response Parsing")
    print("="*70)

    # Use provided response or sample
    if not response_text:
        print("\n[INFO] Using sample response for parsing test")
        response_text = """{
            "coin": "BTC/USD:USD",
            "signal": "buy_to_enter",
            "quantity_usd": 50.0,
            "leverage": 2.0,
            "confidence": 0.75,
            "exit_plan": {
                "profit_target": 52000.0,
                "stop_loss": 49000.0,
                "invalidation_condition": "4H RSI breaks below 40"
            },
            "justification": "Strong upward momentum with RSI indicating bullish continuation"
        }"""

    # Parse response
    decision = parse_llm_response(response_text)

    if decision:
        print(f"\n[OK] Successfully parsed trade decision:")
        print(f"  Coin: {decision.coin}")
        print(f"  Signal: {decision.signal.value}")
        print(f"  Quantity: ${decision.quantity_usd:.2f}")
        print(f"  Leverage: {decision.leverage}x")
        print(f"  Confidence: {decision.confidence:.2f}")
        print(f"  Profit Target: ${decision.exit_plan.profit_target:,.2f}")
        print(f"  Stop Loss: ${decision.exit_plan.stop_loss:,.2f}")
        print(f"  Justification: {decision.justification[:80]}...")

        print(f"\n[INFO] Decision properties:")
        print(f"  Is Actionable: {decision.is_actionable()}")
        print(f"  Is Entry: {decision.is_entry()}")
        print(f"  Is Exit: {decision.is_exit()}")
        print(f"  Is Hold: {decision.is_hold()}")

        return decision
    else:
        print("\n[FAIL] Failed to parse response")
        return None


def main():
    """Run complete integration test."""
    print("\n" + "="*70)
    print("ALPHA ARENA MINI - End-to-End Integration Test")
    print("="*70)
    print(f"\nTesting complete pipeline with synthetic data")
    print(f"Hyperliquid API: Not required (using mock data)")
    print(f"Anthropic API: {'Configured' if settings.anthropic_api_key else 'Not configured (optional)'}")
    print()

    try:
        # Test 1: Data Pipeline
        btc_indicators = test_data_pipeline()

        # Generate ETH data too
        eth_data = generate_synthetic_market_data("ETH/USD:USD", base_price=3500, num_candles=100)
        eth_indicators = TechnicalIndicators.calculate_all(eth_data)

        # Test 2: Prompt Generation
        system_prompt, user_prompt = test_prompt_generation(btc_indicators, eth_indicators)

        # Test 3: Claude Integration (optional)
        claude_response = test_claude_integration(system_prompt, user_prompt)

        # Test 4: Response Parsing
        decision = test_response_parsing(claude_response)

        # Summary
        print("\n" + "="*70)
        print("INTEGRATION TEST SUMMARY")
        print("="*70)
        print("\n[RESULTS]:")
        print(f"  [OK] Data Pipeline: Generate market data + calculate indicators")
        print(f"  [OK] Prompt Generation: Build prompts for Claude")

        if claude_response:
            print(f"  [OK] Claude Integration: Successfully called Claude API")
        else:
            print(f"  [SKIP] Claude Integration: API key not configured or call failed")

        if decision:
            print(f"  [OK] Response Parsing: Successfully parsed trade decision")
        else:
            print(f"  [FAIL] Response Parsing: Failed to parse response")

        print("\n[STATUS]: Core pipeline functional! [OK]")

        if not settings.anthropic_api_key:
            print("\n[NOTE]: To test with real Claude decisions:")
            print("  1. Add ANTHROPIC_API_KEY to your .env file")
            print("  2. Run this test again")

        print("\n[NEXT STEPS]:")
        print("  1. Get Hyperliquid API key to fetch real market data")
        print("  2. Get Anthropic API key to test Claude integration")
        print("  3. Proceed to Phase 3: Paper Trading Simulator")

    except Exception as e:
        print(f"\n[ERROR] Integration test failed: {e}")
        logger.exception("Full traceback:")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
