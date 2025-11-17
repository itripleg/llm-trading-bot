#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test with REAL market data from Hyperliquid.

Fetches live BTC/ETH/SOL prices and indicators,
sends to Claude for analysis.

No Hyperliquid API key needed - uses public market data!
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.fetcher import MarketDataFetcher
from data.indicators import TechnicalIndicators
from llm.client import ClaudeClient
from llm.prompts import get_system_prompt, build_user_prompt
from llm.parser import parse_llm_response
from trading.logger import TradingLogger

print("=" * 70)
print("TESTING WITH REAL HYPERLIQUID MARKET DATA")
print("=" * 70)
print()

# Initialize fetcher (no API key needed for public data)
print("[1/5] Initializing market data fetcher...")
fetcher = MarketDataFetcher()
print("  [OK] Connected to Hyperliquid")
print()

# Fetch real market data for BTC
print("[2/5] Fetching REAL market data for BTC/USDC...")
btc_ohlcv = fetcher.fetch_ohlcv('BTC/USDC:USDC', timeframe='3m', limit=100)

if btc_ohlcv.empty:
    print("  [FAIL] Could not fetch BTC data")
    sys.exit(1)

print(f"  [OK] Fetched {len(btc_ohlcv)} candles")
print(f"  Current BTC Price: ${btc_ohlcv['close'].iloc[-1]:,.2f}")
print(f"  24h Range: ${btc_ohlcv['low'].min():,.2f} - ${btc_ohlcv['high'].max():,.2f}")
print()

# Calculate indicators
print("[3/5] Calculating technical indicators...")
btc_with_indicators = TechnicalIndicators.calculate_all(btc_ohlcv)

latest = btc_with_indicators.iloc[-1]
print(f"  EMA-20: ${latest.get('ema_20', 0):,.2f}")
print(f"  RSI-14: {latest.get('rsi_14', 0):.2f}")
print(f"  MACD: {latest.get('macd', 0):.2f}")
print()

# Build prompt
print("[4/5] Building trading prompt...")
market_data = {
    'BTC/USDC:USDC': {
        'current_price': btc_with_indicators['close'].iloc[-1],
        'ohlcv': btc_with_indicators,
        'indicators': btc_with_indicators,
        'funding_rate': 0.0001,  # Would fetch from API if we had credentials
        'open_interest': None,
    }
}

account_state = {
    'available_cash': 10000.0,
    'total_value': 10000.0,
    'total_return_pct': 0.0,
    'sharpe_ratio': 0.0,
    'positions': [],
}

system_prompt = get_system_prompt()
user_prompt = build_user_prompt(market_data, account_state, 0)

print(f"  [OK] Prompt ready ({len(system_prompt) + len(user_prompt)} chars)")
print()

# Get Claude's decision
print("[5/5] Getting Claude's trading decision...")
print("  (This may take 10-30 seconds...)")
print()

client = ClaudeClient()
response = client.get_trading_decision(system_prompt, user_prompt)

if not response:
    print("  [FAIL] No response from Claude")
    sys.exit(1)

# Save response
with open('logs/real_data_response.txt', 'w', encoding='utf-8') as f:
    f.write(response)
print("  [OK] Response saved to logs/real_data_response.txt")
print()

# Parse decision
decision = parse_llm_response(response)

if not decision:
    print("  [FAIL] Could not parse Claude's response")
    print(f"  Raw response: {response[:500]}...")
    sys.exit(1)

# Log decision and account state to database
print("  [OK] Logging decision to database...")
logger = TradingLogger()
logger.log_decision_from_trade_decision(decision, raw_response=response)
logger.log_account_state(
    balance=account_state['available_cash'],
    equity=account_state['total_value'],
    unrealized_pnl=0.0,
    realized_pnl=0.0,
    sharpe_ratio=account_state.get('sharpe_ratio', 0.0),
    num_positions=len(account_state['positions'])
)
logger.log_bot_status('running', 'Test run with real market data')
print("  [OK] Data logged to database")

# Display decision
print("=" * 70)
print("CLAUDE'S TRADING DECISION (Based on REAL market data)")
print("=" * 70)
print()
print(f"Coin: {decision.coin}")
print(f"Signal: {decision.signal.value.upper()}")
print(f"Quantity: ${decision.quantity_usd:.2f}")
print(f"Leverage: {decision.leverage}x")
print(f"Confidence: {decision.confidence:.0%}")
print()

if decision.exit_plan.profit_target:
    print(f"Profit Target: ${decision.exit_plan.profit_target:,.2f}")
if decision.exit_plan.stop_loss:
    print(f"Stop Loss: ${decision.exit_plan.stop_loss:,.2f}")
if decision.exit_plan.invalidation_condition:
    print(f"Invalidation: {decision.exit_plan.invalidation_condition}")
print()

print("Justification:")
print("-" * 70)
print(decision.justification)
print("-" * 70)
print()

print("=" * 70)
print("SUCCESS: Full pipeline working with real market data!")
print("=" * 70)
