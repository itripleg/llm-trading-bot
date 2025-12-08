import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

@dataclass
class TradingConfig:
    """
    Configuration for the trading session to ensure platform/exchange agnosticism.
    """
    exchange_name: str = "Hyperliquid"
    asset_class: str = "Perpetual Futures"
    min_position_size_usd: float = 10.0
    max_leverage: float = 20.0
    # The columns in the dataframe that should be highlighted in the prompt
    relevant_indicators: List[str] = field(default_factory=lambda: ['ema_20', 'macd', 'rsi_7', 'rsi_14', 'volume'])

class PromptBuilder:
    """
    Build prompts for LLM trading decisions.
    Now instantiated with a config to allow for dynamic constraints.
    """

    def __init__(self, config: TradingConfig):
        self.config = config

    def _generate_system_prompt_template(self) -> str:
        """
        Dynamically generates the system prompt based on constraints.
        """
        return f"""You are an autonomous cryptocurrency trading agent operating on the {self.config.exchange_name} exchange.

Your goal is to maximize profit and loss (PnL) while managing risk appropriately. You have been given real capital to trade.

## Operational Constraints (CRITICAL)
- **Minimum Position Size:** ${self.config.min_position_size_usd:.2f} USD (Trades below this will fail).
- **Maximum Leverage:** {self.config.max_leverage}x (Do not exceed this leverage).
- **Asset Class:** {self.config.asset_class}.

## Your Capabilities
- Analyze technical indicators provided in the context.
- Open long or short positions.
- Manage multiple positions across different assets.

## Trading Rules
1. STRICTLY adhere to the minimum position size of ${self.config.min_position_size_usd}.
2. NEVER exceed daily loss limits.
3. Set clear exit plans for every position (profit target, stop loss, invalidation).
4. Be explicit about confidence levels (0.0 to 1.0).
5. Provide clear justification for every decision.

## Trade Conviction & Position Management
- **High confidence (≥70%):** Aggressively target the move. Use higher leverage (5x-10x) to maximize returns on high-probability setups.
- **Medium confidence (50-69%):** Standard sizing. Use moderate leverage (2x-4x).
- **Low confidence (<50%):** Stay out or use minimal size/leverage.
- **Diamond Hands:** Once in a trade, HOLD until the trend is clearly broken. Do NOT exit on small red candles or minor chop.
- Only exit early if:
  1. Market structure is BROKEN (e.g., lower low in an uptrend).
  2. Hard stop loss is hit.
  3. Profit target is hit.
  4. You typically should NOT exit just because the price stalled for a few candles. Give the trade room to breathe.

## Strategy Guidelines (Aggressive Trend Following)
- **Aggression:** You are an aggressive trader. If the chart is bullish, you are LONG. If bearish, you are SHORT. Do not sit on the sidelines without a very good reason.
- **Leverage:** Use 5x-10x leverage for high conviction setups. We are here to make money, not to play it safe.
- **Sizing:** Deploy capital decisively. Do not "dip a toe". Enter with conviction.
- **Risk:** The biggest risk is missing the pump. While we use stops, we accept volatility as the cost of doing business.
- **Persistence:** If stopped out but the thesis remains valid (e.g., a wick fakeout), RE-ENTER immediately. Do not be afraid to be wrong, be afraid to stay out of a winning trend.

## Output Format
Return valid JSON with these exact fields:
{{
    "coin": "BTC/USDC:USDC",
    "signal": "buy_to_enter|sell_to_enter|hold|close",
    "quantity_usd": 50.0,
    "leverage": 2.0,
    "confidence": 0.75,
    "exit_plan": {{
        "profit_target": 0.0,
        "stop_loss": 0.0,
        "invalidation_condition": "Reason text"
    }},
    "justification": "Clear technical analysis reasoning"
}}

CRITICAL: Use the EXACT symbol format from the market data section (e.g., "BTC/USDC:USDC", "ETH/USDC:USDC", "ARB/USDC:USDC", "SOL/USDC:USDC"). Do NOT shorten to "BTC", "ETH", "ARB" etc.

IMPORTANT: Data provided below is ordered OLDEST → NEWEST."""

    def format_market_data(
        self,
        symbol: str,
        current_price: float,
        indicators_df: pd.DataFrame,
        funding_rate: Optional[float] = None,
        open_interest: Optional[float] = None,
    ) -> str:
        """
        Format market data for a single asset.
        """
        lines = []
        lines.append(f"### {symbol} DATA")
        lines.append("")

        # Current state
        latest = indicators_df.iloc[-1] if not indicators_df.empty else {}
        
        # specific header stats
        header_stats = [f"current_price = {current_price:.2f}"]
        for col in ['ema_20', 'macd', 'rsi_7']:
            if col in latest:
                val = latest[col]
                header_stats.append(f"current_{col} = {val:.4f}" if isinstance(val, (float, int)) else f"current_{col} = {val}")
        
        lines.append(", ".join(header_stats))
        lines.append("")

        # Funding rate and open interest
        if funding_rate is not None or open_interest is not None:
            lines.append(f"Open Interest & Funding Rate:")
            if open_interest is not None:
                lines.append(f"Open Interest: Latest: {open_interest:.2f}")
            if funding_rate is not None:
                lines.append(f"Funding Rate: {funding_rate:.8f}")
            lines.append("")

        # Intraday series
        lines.append("**Intraday series (oldest → latest):**")
        lines.append("")

        if not indicators_df.empty:
            # We take the last 15 rows for context
            last_n = indicators_df.tail(15)

            # Prices
            if 'close' in last_n.columns:
                prices = last_n['close'].tolist()
                lines.append(f"Close prices: {[round(p, 2) for p in prices]}")
                lines.append("")

            # Dynamic Indicator Formatting
            # This iterates through columns defined in config, making it model-agnostic
            for col in self.config.relevant_indicators:
                if col in last_n.columns:
                    # Clean nans and round
                    vals = last_n[col].dropna().tolist()
                    if vals:
                        rounded = [round(v, 3) if isinstance(v, (int, float)) else v for v in vals]
                        lines.append(f"{col.upper()}: {rounded}")
                        lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def format_account_state(
        self,
        available_cash: float,
        total_value: float,
        positions: List[Dict[str, Any]],
        total_return_pct: float,
        sharpe_ratio: float,
        trade_history: Optional[List[Dict[str, Any]]] = None,
        recent_decisions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Format current account state.
        """
        lines = []
        lines.append("### ACCOUNT INFORMATION & PERFORMANCE")
        lines.append("")
        lines.append(f"Current Total Return: {total_return_pct:.2f}%")
        lines.append(f"Available Cash: ${available_cash:.2f}")
        lines.append(f"Total Account Value: ${total_value:.2f}")
        lines.append("")

        if positions:
            lines.append("CURRENT LIVE POSITIONS:")
            lines.append("")
            for pos in positions:
                # Basic info
                lines.append(f"Position: {pos['coin']} ({pos['side'].upper()})")
                lines.append(f"  Entry: ${pos['entry_price']:,.2f} | Current: ${pos['current_price']:,.2f}")
                lines.append(f"  Size: ${pos['quantity_usd']:.2f} (Lev: {pos['leverage']}x)")
                lines.append(f"  Unrealized P&L: ${pos['unrealized_pnl']:+,.2f}")
                
                # Check for exit plans
                if 'profit_target' in pos or 'stop_loss' in pos:
                     lines.append("  Exit Plan:")
                     if pos.get('profit_target'):
                         lines.append(f"    - Target: ${pos['profit_target']:,.2f}")
                     if pos.get('stop_loss'):
                         lines.append(f"    - Stop: ${pos['stop_loss']:,.2f}")
                
                lines.append("")
        else:
            lines.append("No active positions.")
            lines.append("")

        lines.append(f"Risk Metric (Sharpe): {sharpe_ratio:.3f}")
        
        return "\n".join(lines)

    def build_trading_prompt(
        self,
        market_data: Dict[str, Dict],
        account_state: Dict[str, Any],
        minutes_since_start: int = 0,
        user_guidance: Optional[str] = None,
    ) -> str:
        """
        Build the User Prompt (Context).
        """
        lines = []

        # Header
        lines.append(f"Trading Session Duration: {minutes_since_start} minutes.")
        lines.append("Analyze the provided state data and predictive signals.")
        lines.append(f"REMINDER: Minimum order size is ${self.config.min_position_size_usd}.")
        lines.append("")
        
        # Supervisor Guidance (High Priority)
        if user_guidance:
            lines.append("!!! SUPERVISOR GUIDANCE (HIGH PRIORITY) !!!")
            lines.append("The human supervisor has provided the following context/instruction:")
            lines.append(f"> \"{user_guidance}\"")
            lines.append("You MUST consider this input in your analysis and decision making.")
            lines.append("If this guidance contradicts standard rules, prioritize this guidance (within safety limits).")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Current market state
        lines.append("### CURRENT MARKET DATA")
        lines.append("")

        # Add market data for each asset
        for symbol, data in market_data.items():
            market_section = self.format_market_data(
                symbol=symbol,
                current_price=data.get('current_price', 0),
                indicators_df=data.get('indicators', pd.DataFrame()),
                funding_rate=data.get('funding_rate'),
                open_interest=data.get('open_interest'),
            )
            lines.append(market_section)

        # Account state
        account_section = self.format_account_state(
            available_cash=account_state.get('available_cash', 0),
            total_value=account_state.get('total_value', 0),
            positions=account_state.get('positions', []),
            total_return_pct=account_state.get('total_return_pct', 0),
            sharpe_ratio=account_state.get('sharpe_ratio', 0),
            trade_history=account_state.get('trade_history', None),
            recent_decisions=account_state.get('recent_decisions', None),
        )
        lines.append(account_section)

        lines.append("---")
        lines.append("")
        lines.append("Based on this data, make your trading decision. Ensure all constraints are met. Return valid JSON only.")

        return "\n".join(lines)

    def get_system_prompt(self) -> str:
        return self._generate_system_prompt_template()


# --------------------------------------------------------------------------
# USAGE EXAMPLE
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("Dynamic Prompt Builder Test")
    print("=" * 70)

    # 1. DEFINE CONFIGURATION
    # We inject the constraints here rather than hardcoding them in the class
    hyperliquid_config = TradingConfig(
        exchange_name="Hyperliquid",
        min_position_size_usd=10.0,  # User specified
        max_leverage=10.0,           # User specified
        relevant_indicators=['ema_20', 'rsi_14', 'macd', 'volume']
    )

    # 2. INSTANTIATE BUILDER
    builder = PromptBuilder(config=hyperliquid_config)

    # 3. MOCK DATA
    sample_data = pd.DataFrame({
        'close': np.random.uniform(50000, 51000, 20),
        'ema_20': np.random.uniform(50000, 51000, 20),
        'rsi_14': np.random.uniform(30, 70, 20),
        'macd': np.random.uniform(-50, 50, 20),
        'volume': np.random.uniform(100, 500, 20)
    })

    market_data = {
        'BTC-PERP': {
            'current_price': 50500.0,
            'indicators': sample_data,
            'funding_rate': 0.0001,
            'open_interest': 1000000.0
        }
    }
    
    account_state = {
        'available_cash': 1000.0,
        'total_value': 1000.0,
        'positions': [],
        'total_return_pct': 0.0,
        'sharpe_ratio': 0.0
    }

    # 4. GENERATE PROMPTS
    sys_prompt = builder.get_system_prompt()
    user_prompt = builder.build_trading_prompt(market_data, account_state, minutes_since_start=15)

    print("\n--- SYSTEM PROMPT SNIPPET ---")
    print(sys_prompt[:600] + "...\n") # Showing the constraint injection
    
    print("\n--- USER PROMPT SNIPPET ---")
    print(user_prompt[:600] + "...\n")
