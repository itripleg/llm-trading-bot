"""
Trading prompt presets for different strategies and risk profiles.

Each preset defines a complete trading strategy with specific rules,
risk management, and position sizing guidelines.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PromptPreset:
    """A trading strategy preset."""
    name: str
    description: str
    strategy_section: str
    sizing_rules: str
    risk_rules: str
    exit_rules: str


# =============================================================================
# PRESET DEFINITIONS
# =============================================================================

PRESETS: Dict[str, PromptPreset] = {
    "aggressive_small_account": PromptPreset(
        name="Aggressive Small Account (<$20)",
        description="High-risk, all-or-nothing strategy for accounts under $20. Uses maximum leverage on high-conviction setups.",
        strategy_section="""## Strategy: Aggressive Small Account (All-or-Nothing)

**Philosophy:** With a small account (<$20), we use HIGH LEVERAGE to turn small capital into meaningful positions. This is a high-risk, high-reward approach designed to grow small accounts quickly.

**Key Principles:**
- SMALL POSITIONS ARE VALID: $1-2 positions with 20-25x leverage = $20-50 exposure
- Use cross-margin: Account acts as collateral, enabling multiple small trades
- Focus on HIGH CONVICTION setups only (>70% confidence)
- Accept that we may lose the account, but the upside is 5-10x growth
- Take DECISIVE action - don't sit on the sidelines with such a small account""",

        sizing_rules="""## Position Sizing for Small Accounts

**Capital Allocation:**
- Balance < $5: Use 80-100% per trade (all-in on best setup)
- Balance $5-$10: Use 50-80% per trade
- Balance $10-$20: Use 30-50% per trade
- Minimum position: $1 (with leverage, this is $10-20 exposure)

**Leverage Strategy:**
- High conviction (>80%): Use 20-25x leverage
- Medium conviction (60-80%): Use 15-20x leverage
- Lower conviction (<60%): Skip or use 5-10x leverage

**Example Trades:**
- $2 position @ 25x = $50 notional exposure
- $1 position @ 20x = $20 notional exposure
- Goal: 10+ trades to find the winner that 3-5x's the account""",

        risk_rules="""## Risk Management (Aggressive)

**Stop Losses:**
- Use TIGHT stops (5-10% from entry) to preserve capital for next trades
- Expect to get stopped out frequently - this is normal
- Re-enter if thesis remains valid after stop out

**Position Management:**
- ONE position at a time (all-in mentality)
- No hedging, no portfolio theory - pure directional bets
- If a trade is working, HOLD until clear reversal (not just a wick)

**Daily Limits:**
- Max 3 losing trades per day before reassessing
- If account drops below $1, stop trading for the day""",

        exit_rules="""## Exit Strategy (Let Winners Run)

**Profit Taking:**
- First target: 2-3R (risk-reward ratio)
- Scale out: Take 50% at first target, let rest run
- Trail stop on remaining 50% using EMA-20 or key support/resistance

**Stop Loss Hits:**
- Accept the loss immediately, no averaging down
- Wait 15-30 minutes before next trade (avoid revenge trading)
- If stopped out 3 times on same coin, switch to different asset

**When to Close Early:**
1. Market structure clearly broken (e.g., lower low in uptrend)
2. Major news event that invalidates thesis
3. Hard stop loss hit
4. Otherwise: DIAMOND HANDS - hold through volatility"""
    ),

    "standard": PromptPreset(
        name="Standard Balanced",
        description="Balanced risk/reward for accounts $20-$100. Moderate leverage with proper risk management.",
        strategy_section="""## Strategy: Balanced Trading

**Philosophy:** Balance growth with capital preservation. Use moderate leverage on quality setups.

**Key Principles:**
- Risk 2-5% of account per trade
- Use 5-10x leverage on high conviction setups
- Maintain 2-3 positions maximum
- Focus on risk-adjusted returns, not just absolute returns""",

        sizing_rules="""## Position Sizing (Balanced)

**Capital Allocation:**
- Per trade: 20-30% of account value
- Maximum 3 concurrent positions
- Minimum position: $10

**Leverage Strategy:**
- High conviction (>80%): 8-10x leverage
- Medium conviction (60-80%): 5-7x leverage
- Low conviction (<60%): 2-3x leverage or skip""",

        risk_rules="""## Risk Management (Balanced)

**Stop Losses:**
- Always use stops: 2-5% from entry
- Never risk more than 5% of account on one trade
- Use position sizing to control risk

**Position Management:**
- Max 3 positions across different assets
- Correlation check: Don't hold 3 positions in same direction
- Rebalance if any position grows >40% of portfolio""",

        exit_rules="""## Exit Strategy (Balanced)

**Profit Taking:**
- Take 30% at 1.5R
- Take 30% at 2.5R
- Trail stop on remaining 40%

**Stop Loss Management:**
- Move to breakeven after 1R gain
- Trail with EMA-20 or swing lows/highs"""
    ),

    "conservative": PromptPreset(
        name="Conservative Capital Preservation",
        description="Low-risk strategy for larger accounts ($100+). Focus on capital preservation with limited leverage.",
        strategy_section="""## Strategy: Conservative Capital Preservation

**Philosophy:** Protect capital first, grow second. Use minimal leverage and strict risk controls.

**Key Principles:**
- Risk only 1-2% per trade
- Use 2-5x leverage maximum
- Focus on high-probability setups only (>75% confidence)
- Never hold more than 3 positions""",

        sizing_rules="""## Position Sizing (Conservative)

**Capital Allocation:**
- Per trade: 10-20% of account value
- Maximum 3 concurrent positions
- Minimum position: $20

**Leverage Strategy:**
- High conviction (>85%): 4-5x leverage
- Medium conviction (75-85%): 2-3x leverage
- Low conviction: Skip trade""",

        risk_rules="""## Risk Management (Conservative)

**Stop Losses:**
- Always use stops: 1-2% account risk
- Wide stops to avoid noise (3-5% from entry)
- Never move stops against position

**Position Management:**
- Max 3 positions, diversified assets
- If 2 positions losing, don't open third
- Close all positions if account drops 5% in a day""",

        exit_rules="""## Exit Strategy (Conservative)

**Profit Taking:**
- Take 50% at 1.5R
- Take 30% at 2R
- Trail stop on final 20%

**Stop Loss Management:**
- Move to breakeven after 1R
- Use time stops: Close if no progress in 4 hours"""
    ),
}


def get_preset(preset_name: str = "aggressive_small_account") -> PromptPreset:
    """
    Get a prompt preset by name.

    Args:
        preset_name: Name of the preset

    Returns:
        PromptPreset object
    """
    return PRESETS.get(preset_name, PRESETS["aggressive_small_account"])


def list_presets() -> Dict[str, str]:
    """
    List all available presets.

    Returns:
        Dict of {preset_key: preset_name}
    """
    return {key: preset.name for key, preset in PRESETS.items()}


def get_preset_description(preset_name: str) -> str:
    """
    Get description of a preset.

    Args:
        preset_name: Name of the preset

    Returns:
        Description string
    """
    preset = PRESETS.get(preset_name)
    return preset.description if preset else "Unknown preset"
