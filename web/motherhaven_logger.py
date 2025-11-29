"""
Motherhaven API Logger - POSTs trading data to the Motherhaven Next.js frontend.

This logger sends data to the Firebase-backed Next.js API for real-time monitoring
via the modern Motherhaven dashboard. SQLite remains as local backup.
"""

import requests
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MotherhavenLogger:
    """
    Logger that POSTs trading bot data to Motherhaven API endpoints.

    Expected endpoints:
    - POST /api/llm-bot/ingest/decision
    - POST /api/llm-bot/ingest/position
    - POST /api/llm-bot/ingest/account
    - POST /api/llm-bot/ingest/status
    """

    def __init__(self, base_url: str, api_key: str, enabled: bool = True, timeout: int = 10):
        """
        Initialize the Motherhaven logger.

        Args:
            base_url: Base URL of the Motherhaven API (e.g., http://localhost:3000)
            api_key: API key for x-api-key header authentication
            enabled: If False, logger will no-op (useful for testing)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.enabled = enabled
        self.timeout = timeout

        if not self.enabled:
            logger.info("[Motherhaven] Logger disabled - no data will be sent to API")
        else:
            logger.info(f"[Motherhaven] Logger initialized - posting to {self.base_url}")

    def _post(self, endpoint: str, data: Dict[str, Any]) -> bool:
        """
        Internal method to POST data to an endpoint.

        Args:
            endpoint: API endpoint (e.g., /api/llm-bot/ingest/decision)
            data: JSON data to POST

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                logger.debug(f"[Motherhaven] Successfully posted to {endpoint}")
                return True
            else:
                logger.warning(
                    f"[Motherhaven] Failed to post to {endpoint}: "
                    f"Status {response.status_code}, Response: {response.text[:200]}"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error(f"[Motherhaven] Timeout posting to {endpoint} after {self.timeout}s")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"[Motherhaven] Connection error posting to {endpoint} - is the API running?")
            return False
        except Exception as e:
            logger.error(f"[Motherhaven] Unexpected error posting to {endpoint}: {e}")
            return False

    def log_decision(
        self,
        decision_data: Dict[str, Any],
        raw_response: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None
    ) -> bool:
        """
        Log a Claude trading decision to Motherhaven.

        Args:
            decision_data: Dictionary with keys matching TradeDecision model
            raw_response: Optional raw JSON response from Claude
            system_prompt: Optional system prompt sent to Claude
            user_prompt: Optional user prompt sent to Claude

        Returns:
            True if successfully posted
        """
        exit_plan = decision_data.get('exit_plan', {}) or {}

        payload = {
            "timestamp": datetime.now().isoformat(),
            "coin": decision_data['coin'],
            "signal": decision_data['signal'],
            "quantity_usd": float(decision_data['quantity_usd']),
            "leverage": float(decision_data['leverage']),
            "confidence": float(decision_data['confidence']),
            "justification": decision_data['justification']
        }

        # Add optional exit plan fields
        if exit_plan.get('profit_target'):
            payload['profit_target'] = float(exit_plan['profit_target'])
        if exit_plan.get('stop_loss'):
            payload['stop_loss'] = float(exit_plan['stop_loss'])
        if exit_plan.get('invalidation_condition'):
            payload['invalidation_condition'] = exit_plan['invalidation_condition']

        # Add raw response if available
        if raw_response:
            payload['raw_response'] = raw_response

        # Add prompts if available
        if system_prompt:
            payload['system_prompt'] = system_prompt
        if user_prompt:
            payload['user_prompt'] = user_prompt

        return self._post("/api/llm-bot/ingest/decision", payload)

    def log_position_entry(
        self,
        position_id: str,
        coin: str,
        side: str,
        entry_price: float,
        quantity_usd: float,
        leverage: float
    ) -> bool:
        """
        Log a new position entry to Motherhaven.

        Args:
            position_id: Unique position identifier
            coin: Trading pair (e.g., BTC/USD:USD)
            side: 'long' or 'short'
            entry_price: Entry price
            quantity_usd: Position size in USD
            leverage: Leverage multiplier

        Returns:
            True if successfully posted
        """
        payload = {
            "coin": coin,
            "side": side,
            "quantity_usd": float(quantity_usd),
            "leverage": float(leverage),
            "entry_price": float(entry_price),
            "entry_time": datetime.now().isoformat(),
            "status": "open"
        }

        return self._post("/api/llm-bot/ingest/position", payload)

    def log_position_exit(
        self,
        position_id: str,
        coin: str,
        side: str,
        entry_price: float,
        entry_time: str,
        exit_price: float,
        quantity_usd: float,
        leverage: float,
        realized_pnl: float
    ) -> bool:
        """
        Log a position exit to Motherhaven.

        Args:
            position_id: Unique position identifier
            coin: Trading pair
            side: 'long' or 'short'
            entry_price: Original entry price
            entry_time: Original entry time (ISO format)
            exit_price: Exit price
            quantity_usd: Position size in USD
            leverage: Leverage multiplier
            realized_pnl: Realized profit/loss

        Returns:
            True if successfully posted
        """
        payload = {
            "coin": coin,
            "side": side,
            "quantity_usd": float(quantity_usd),
            "leverage": float(leverage),
            "entry_price": float(entry_price),
            "entry_time": entry_time,
            "exit_price": float(exit_price),
            "exit_time": datetime.now().isoformat(),
            "realized_pnl": float(realized_pnl),
            "status": "closed"
        }

        return self._post("/api/llm-bot/ingest/position", payload)

    def log_account_state(
        self,
        balance_usd: float,
        equity_usd: float,
        unrealized_pnl: float = 0,
        realized_pnl: float = 0,
        sharpe_ratio: Optional[float] = None,
        num_positions: int = 0
    ) -> bool:
        """
        Log account state snapshot to Motherhaven.

        Args:
            balance_usd: Current balance
            equity_usd: Total equity (balance + unrealized PnL)
            unrealized_pnl: Unrealized profit/loss
            realized_pnl: Realized profit/loss
            sharpe_ratio: Optional Sharpe ratio
            num_positions: Number of open positions

        Returns:
            True if successfully posted
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "balance_usd": float(balance_usd),
            "equity_usd": float(equity_usd),
            "unrealized_pnl": float(unrealized_pnl),
            "realized_pnl": float(realized_pnl),
            "total_pnl": float(unrealized_pnl + realized_pnl),
            "num_positions": int(num_positions)
        }

        # Add optional Sharpe ratio
        if sharpe_ratio is not None:
            payload['sharpe_ratio'] = float(sharpe_ratio)

        return self._post("/api/llm-bot/ingest/account", payload)

    def log_status(
        self,
        status: str,
        message: Optional[str] = None,
        trades_today: Optional[int] = None,
        pnl_today: Optional[float] = None
    ) -> bool:
        """
        Log bot status to Motherhaven.

        Args:
            status: Status string (e.g., 'running', 'stopped', 'error')
            message: Optional status message
            trades_today: Optional number of trades today
            pnl_today: Optional P&L for today

        Returns:
            True if successfully posted
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "message": message or ""
        }

        # Add optional metrics
        if trades_today is not None:
            payload['trades_today'] = int(trades_today)
        if pnl_today is not None:
            payload['pnl_today'] = float(pnl_today)

        return self._post("/api/llm-bot/ingest/status", payload)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    import sys

    # Enable debug logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Test configuration
    BASE_URL = "http://localhost:3000"
    API_KEY = "test-api-key-12345"

    print("="*60)
    print("Motherhaven Logger Test")
    print("="*60)
    print(f"Target URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:10]}...")
    print()

    # Initialize logger
    mh_logger = MotherhavenLogger(
        base_url=BASE_URL,
        api_key=API_KEY,
        enabled=True
    )

    # Test 1: Log a decision
    print("Test 1: Logging decision...")
    decision = {
        'coin': 'BTC/USD:USD',
        'signal': 'buy_to_enter',
        'quantity_usd': 50.0,
        'leverage': 2.0,
        'confidence': 0.75,
        'exit_plan': {
            'profit_target': 111000.0,
            'stop_loss': 106361.0,
            'invalidation_condition': '4H RSI breaks below 40'
        },
        'justification': 'Strong bullish momentum with RSI confirmation'
    }
    success = mh_logger.log_decision(decision, raw_response='{"signal": "buy_to_enter"}')
    print(f"Result: {'✓ Success' if success else '✗ Failed'}\n")

    # Test 2: Log position entry
    print("Test 2: Logging position entry...")
    success = mh_logger.log_position_entry(
        position_id="BTC_20250117_001",
        coin="BTC/USD:USD",
        side="long",
        entry_price=99798.0,
        quantity_usd=50.0,
        leverage=2.0
    )
    print(f"Result: {'✓ Success' if success else '✗ Failed'}\n")

    # Test 3: Log account state
    print("Test 3: Logging account state...")
    success = mh_logger.log_account_state(
        balance_usd=1000.0,
        equity_usd=1050.0,
        unrealized_pnl=50.0,
        realized_pnl=0.0,
        sharpe_ratio=1.5,
        num_positions=1
    )
    print(f"Result: {'✓ Success' if success else '✗ Failed'}\n")

    # Test 4: Log bot status
    print("Test 4: Logging bot status...")
    success = mh_logger.log_status(
        status="running",
        message="Bot started successfully",
        trades_today=3,
        pnl_today=25.50
    )
    print(f"Result: {'✓ Success' if success else '✗ Failed'}\n")

    # Test 5: Log position exit
    print("Test 5: Logging position exit...")
    success = mh_logger.log_position_exit(
        position_id="BTC_20250117_001",
        coin="BTC/USD:USD",
        side="long",
        entry_price=99798.0,
        entry_time="2025-01-17T10:30:00",
        exit_price=100500.0,
        quantity_usd=50.0,
        leverage=2.0,
        realized_pnl=14.03
    )
    print(f"Result: {'✓ Success' if success else '✗ Failed'}\n")

    print("="*60)
    print("Test completed!")
    print("Note: Tests will fail if Motherhaven API is not running.")
    print("Start the API with: cd ../motherhaven && npm run dev")
    print("="*60)
