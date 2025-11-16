"""
Parse and validate LLM responses for trading decisions.

This module provides Pydantic models and parsing functions to validate
Claude's JSON responses and convert them into structured trade decisions.
"""

from enum import Enum
from typing import Optional, Dict, Any
import json
import re
import logging

from pydantic import BaseModel, Field, field_validator, ValidationError


logger = logging.getLogger(__name__)


class TradeSignal(str, Enum):
    """Valid trade signals."""
    BUY_TO_ENTER = "buy_to_enter"
    SELL_TO_ENTER = "sell_to_enter"
    HOLD = "hold"
    CLOSE = "close"


class ExitPlan(BaseModel):
    """Exit plan for a trade."""
    profit_target: Optional[float] = Field(default=None, description="Price target for taking profit")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price")
    invalidation_condition: Optional[str] = Field(default=None, description="Condition that invalidates the trade thesis")

    @field_validator("profit_target", "stop_loss")
    @classmethod
    def validate_positive(cls, v: Optional[float]) -> Optional[float]:
        """Ensure prices are positive when provided."""
        if v is not None and v < 0:
            raise ValueError("Price must be positive")
        return v


class TradeDecision(BaseModel):
    """Structured trade decision from LLM."""

    coin: str = Field(description="Trading pair symbol")
    signal: TradeSignal = Field(description="Trade signal (buy/sell/hold/close)")
    quantity_usd: float = Field(ge=0, description="Position size in USD")
    leverage: float = Field(ge=0, le=20, description="Leverage multiplier (0 for hold/close)")
    confidence: float = Field(ge=0, le=1, description="Confidence score (0-1)")
    exit_plan: ExitPlan = Field(description="Exit plan with targets and stops")
    justification: str = Field(min_length=10, description="Reasoning for the decision")

    @field_validator("coin")
    @classmethod
    def validate_coin_format(cls, v: str) -> str:
        """Validate coin format (e.g., BTC/USD:USD)."""
        if not v or len(v) < 3:
            raise ValueError("Invalid coin symbol")
        return v.upper()

    @field_validator("quantity_usd")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        """Validate quantity is reasonable."""
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        if v > 1000000:
            raise ValueError("Quantity exceeds reasonable limit")
        return v

    @field_validator("leverage")
    @classmethod
    def validate_leverage(cls, v: float, info) -> float:
        """Validate leverage is appropriate for signal type."""
        # Get signal from values dict (if available during validation)
        signal = info.data.get('signal') if hasattr(info, 'data') else None

        # For entry signals, leverage must be > 0
        if signal in [TradeSignal.BUY_TO_ENTER, TradeSignal.SELL_TO_ENTER]:
            if v <= 0:
                raise ValueError("Leverage must be greater than 0 for entry signals")

        # For hold/close, leverage can be 0
        return v

    def is_actionable(self) -> bool:
        """Check if this decision requires action."""
        return self.signal in [TradeSignal.BUY_TO_ENTER, TradeSignal.SELL_TO_ENTER, TradeSignal.CLOSE]

    def is_entry(self) -> bool:
        """Check if this is an entry signal."""
        return self.signal in [TradeSignal.BUY_TO_ENTER, TradeSignal.SELL_TO_ENTER]

    def is_exit(self) -> bool:
        """Check if this is an exit signal."""
        return self.signal == TradeSignal.CLOSE

    def is_hold(self) -> bool:
        """Check if this is a hold signal."""
        return self.signal == TradeSignal.HOLD


class ResponseParser:
    """Parse and validate LLM responses."""

    @staticmethod
    def extract_json(response_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from response text.

        Handles cases where JSON is wrapped in markdown code blocks
        or mixed with explanatory text.

        Args:
            response_text: Raw response from LLM

        Returns:
            Parsed JSON dict or None if extraction fails
        """
        try:
            # Try direct JSON parse first
            return json.loads(response_text)

        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # Try to extract any JSON object
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to extract JSON from response: {response_text[:200]}...")
            return None

    @staticmethod
    def parse_trade_decision(response_text: str) -> Optional[TradeDecision]:
        """
        Parse LLM response into TradeDecision.

        Args:
            response_text: Raw response from Claude

        Returns:
            TradeDecision object or None if parsing fails
        """
        if not response_text:
            logger.error("Empty response text")
            return None

        # Extract JSON
        json_data = ResponseParser.extract_json(response_text)
        if not json_data:
            logger.error("Could not extract JSON from response")
            return None

        # Validate and parse with Pydantic
        try:
            decision = TradeDecision(**json_data)
            logger.info(f"Parsed trade decision: {decision.coin} - {decision.signal.value}")
            logger.debug(f"Decision details: confidence={decision.confidence}, "
                        f"quantity=${decision.quantity_usd}, leverage={decision.leverage}x")
            return decision

        except ValidationError as e:
            logger.error(f"Validation error parsing trade decision: {e}")
            logger.debug(f"JSON data: {json_data}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error parsing trade decision: {e}")
            logger.exception("Full traceback:")
            return None

    @staticmethod
    def validate_decision_against_limits(
        decision: TradeDecision,
        max_position_size: float,
        max_leverage: float,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate trade decision against configured limits.

        Args:
            decision: TradeDecision to validate
            max_position_size: Maximum position size in USD
            max_leverage: Maximum allowed leverage

        Returns:
            (is_valid, error_message) tuple
        """
        # Check position size
        if decision.quantity_usd > max_position_size:
            return False, f"Position size ${decision.quantity_usd:.2f} exceeds limit ${max_position_size:.2f}"

        # Check leverage
        if decision.leverage > max_leverage:
            return False, f"Leverage {decision.leverage}x exceeds limit {max_leverage}x"

        # Check stop loss vs entry for long positions
        if decision.signal == TradeSignal.BUY_TO_ENTER:
            if decision.exit_plan.stop_loss > decision.exit_plan.profit_target:
                return False, "Stop loss is above profit target for long position"

        # Check stop loss vs entry for short positions
        if decision.signal == TradeSignal.SELL_TO_ENTER:
            if decision.exit_plan.stop_loss < decision.exit_plan.profit_target:
                return False, "Stop loss is below profit target for short position"

        return True, None


def parse_llm_response(response_text: str) -> Optional[TradeDecision]:
    """
    Parse LLM response into TradeDecision.

    Convenience function for parsing.

    Args:
        response_text: Raw response from LLM

    Returns:
        TradeDecision object or None
    """
    return ResponseParser.parse_trade_decision(response_text)


if __name__ == "__main__":
    """Test response parser."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 70)
    print("Response Parser Test")
    print("=" * 70)
    print()

    # Test 1: Valid JSON response
    print("Test 1: Parsing valid JSON response...")
    valid_response = """
    {
        "coin": "BTC/USD:USD",
        "signal": "buy_to_enter",
        "quantity_usd": 50.0,
        "leverage": 2.0,
        "confidence": 0.75,
        "exit_plan": {
            "profit_target": 111000.0,
            "stop_loss": 106361.0,
            "invalidation_condition": "4H RSI breaks below 40"
        },
        "justification": "BTC breaking above consolidation with strong momentum"
    }
    """

    decision = parse_llm_response(valid_response)
    if decision:
        print("  [OK] Parsed successfully")
        print(f"    Coin: {decision.coin}")
        print(f"    Signal: {decision.signal.value}")
        print(f"    Quantity: ${decision.quantity_usd:.2f}")
        print(f"    Leverage: {decision.leverage}x")
        print(f"    Confidence: {decision.confidence}")
        print(f"    Actionable: {decision.is_actionable()}")
    else:
        print("  [FAIL] Parse failed")
    print()

    # Test 2: JSON wrapped in markdown
    print("Test 2: Parsing JSON wrapped in markdown...")
    markdown_response = """
    Here's my trading decision:

    ```json
    {
        "coin": "ETH/USD:USD",
        "signal": "hold",
        "quantity_usd": 0,
        "leverage": 1,
        "confidence": 0.5,
        "exit_plan": {
            "profit_target": 0,
            "stop_loss": 0,
            "invalidation_condition": "N/A"
        },
        "justification": "Waiting for clearer signal, mixed indicators currently"
    }
    ```

    Let me know if you need clarification.
    """

    decision = parse_llm_response(markdown_response)
    if decision:
        print("  [OK] Extracted from markdown")
        print(f"    Signal: {decision.signal.value}")
    else:
        print("  [FAIL] Parse failed")
    print()

    # Test 3: Validate against limits
    print("Test 3: Validating decision against limits...")
    if decision:
        is_valid, error = ResponseParser.validate_decision_against_limits(
            decision,
            max_position_size=100.0,
            max_leverage=5.0,
        )
        if is_valid:
            print("  [OK] Decision passes validation")
        else:
            print(f"  [FAIL] Validation failed: {error}")
    print()

    # Test 4: Invalid JSON
    print("Test 4: Handling invalid JSON...")
    invalid_response = "This is not JSON at all!"
    decision = parse_llm_response(invalid_response)
    if decision is None:
        print("  [OK] Correctly handled invalid JSON")
    else:
        print("  [FAIL] Should have returned None")
    print()

    # Test 5: Missing required field
    print("Test 5: Handling missing required field...")
    incomplete_response = """
    {
        "coin": "SOL/USD:USD",
        "signal": "buy_to_enter"
    }
    """
    decision = parse_llm_response(incomplete_response)
    if decision is None:
        print("  [OK] Correctly rejected incomplete data")
    else:
        print("  [FAIL] Should have rejected incomplete data")
    print()

    print("=" * 70)
    print("All parser tests completed!")
    print("=" * 70)
