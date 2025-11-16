"""
LLM client for Anthropic Claude API.

This module provides the ClaudeClient for making trading decisions using
Claude as the reasoning engine. Includes retry logic, error handling, and
comprehensive logging.
"""

from typing import Optional, Dict, Any
import logging
import time
import sys

from anthropic import Anthropic, APIError, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.settings import settings


logger = logging.getLogger(__name__)


class ClaudeClient:
    """Client for interacting with Anthropic Claude API."""

    # Model configuration
    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"  # Latest Claude Sonnet 4.5
    DEFAULT_MAX_TOKENS = 2048
    DEFAULT_TEMPERATURE = 1.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (uses settings if not provided)
            model: Claude model to use (default: claude-sonnet-4-5)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured in settings")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"Initialized Claude client with model {self.model}")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_trading_decision(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[str]:
        """
        Get trading decision from Claude.

        Uses retry logic for rate limits and connection errors.
        Logs all prompts and responses for debugging.

        Args:
            system_prompt: System prompt with instructions
            user_prompt: User prompt with market data

        Returns:
            Claude's response text or None if error
        """
        try:
            start_time = time.time()

            logger.info(f"Sending request to Claude ({self.model})")
            logger.debug(f"System prompt length: {len(system_prompt)} chars")
            logger.debug(f"User prompt length: {len(user_prompt)} chars")

            # Console output for user visibility
            print(f"  -> Sending request to Claude API...", flush=True)
            print(f"  -> Waiting for response (this may take 10-30 seconds)...", flush=True)

            # Make API call
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )

            elapsed = time.time() - start_time
            logger.info(f"Received Claude response in {elapsed:.2f}s")

            # Console output for user visibility
            print(f"  [OK] Response received in {elapsed:.2f}s", flush=True)

            # Extract response text
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
                logger.debug(f"Response length: {len(response_text)} chars")
                logger.debug(f"Response preview: {response_text[:200]}...")

                # Log token usage
                if hasattr(response, 'usage'):
                    logger.info(
                        f"Token usage: input={response.usage.input_tokens}, "
                        f"output={response.usage.output_tokens}"
                    )
                    # Console output for token usage
                    print(f"  [OK] Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out", flush=True)

                return response_text
            else:
                logger.error("No content in Claude response")
                print(f"  [ERROR] No content in Claude response", flush=True)
                return None

        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {e}. Retrying...")
            print(f"  [WARNING] Rate limit exceeded. Retrying...", flush=True)
            raise  # Will be retried by tenacity

        except APIConnectionError as e:
            logger.warning(f"API connection error: {e}. Retrying...")
            print(f"  [WARNING] API connection error. Retrying...", flush=True)
            raise  # Will be retried by tenacity

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            print(f"  [ERROR] Claude API error: {e}", flush=True)
            return None

        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            logger.exception("Full traceback:")
            print(f"  [ERROR] {e}", flush=True)
            sys.stdout.flush()
            return None

    def test_connection(self) -> bool:
        """
        Test API connection with a simple prompt.

        Returns:
            True if connection works, False otherwise
        """
        try:
            logger.info("Testing Claude API connection...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[
                    {
                        "role": "user",
                        "content": "Respond with 'OK' if you can read this.",
                    }
                ],
            )

            if response.content and len(response.content) > 0:
                response_text = response.content[0].text
                logger.info(f"Connection test successful. Response: {response_text[:50]}")
                return True
            else:
                logger.error("Connection test failed: No response content")
                return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_claude_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> ClaudeClient:
    """
    Get or create Claude client instance.

    Args:
        api_key: Optional API key override
        model: Optional model override

    Returns:
        ClaudeClient instance
    """
    return ClaudeClient(api_key=api_key, model=model)


if __name__ == "__main__":
    """Test Claude client."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 70)
    print("Claude Client Test")
    print("=" * 70)
    print()

    try:
        # Test 1: Initialize client
        print("Test 1: Initializing Claude client...")
        client = get_claude_client()
        print(f"  Model: {client.model}")
        print(f"  Max tokens: {client.max_tokens}")
        print(f"  Temperature: {client.temperature}")
        print()

        # Test 2: Test connection
        print("Test 2: Testing API connection...")
        if client.test_connection():
            print("  [OK] Connection successful")
        else:
            print("  [FAIL] Connection failed")
        print()

        # Test 3: Get a simple trading decision
        print("Test 3: Getting sample trading decision...")

        system_prompt = """You are a cryptocurrency trading agent.
Respond with valid JSON containing:
{
    "coin": "BTC/USD:USD",
    "signal": "hold",
    "quantity_usd": 0,
    "leverage": 1,
    "confidence": 0.5,
    "exit_plan": {"profit_target": 0, "stop_loss": 0, "invalidation_condition": "N/A"},
    "justification": "Test response"
}"""

        user_prompt = """BTC is trading at $50,000. What should we do?"""

        response = client.get_trading_decision(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if response:
            print("  [OK] Received response")
            print(f"  Response length: {len(response)} chars")
            print(f"  Response preview: {response[:200]}...")
        else:
            print("  [FAIL] No response received")
        print()

        print("=" * 70)
        print("All tests completed!")
        print("=" * 70)

    except ValueError as e:
        print(f"Configuration error: {e}")
        print()
        print("Make sure ANTHROPIC_API_KEY is set in your .env file")
        print("Example: ANTHROPIC_API_KEY=sk-ant-...")

    except Exception as e:
        print(f"Error during testing: {e}")
        logger.exception("Test failed")
