"""
Configuration management using Pydantic v2 and environment variables.

All configuration is loaded from .env file via python-dotenv.
Environment variables override defaults.
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


class TradingMode(str, Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    """
    Global application settings.

    All settings can be overridden via environment variables.
    Validation ensures configuration is correct before startup.
    """

    # ===== EXCHANGE API CONFIGURATION =====
    # Hyperliquid uses wallet-based authentication
    hyperliquid_wallet_private_key: str = Field(
        default="",
        description="Hyperliquid wallet private key (0x...)"
    )
    hyperliquid_account_address: str = Field(
        default="",
        description="Hyperliquid account address (for API wallets, use main account address)"
    )

    # ===== LLM API CONFIGURATION =====
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic Claude API key"
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI GPT API key"
    )

    # ===== TRADING CONFIGURATION =====
    trading_mode: TradingMode = Field(
        default=TradingMode.PAPER,
        description="Paper (simulated) or live trading mode"
    )
    max_position_size_usd: float = Field(
        default=50.0,
        description="Maximum position size in USD",
        gt=0.0,  # Must be greater than 0
    )
    max_leverage: int = Field(
        default=5,
        description="Maximum leverage allowed",
        gt=0,
        le=20,  # Hyperliquid max is 20x
    )
    daily_loss_limit_usd: float = Field(
        default=20.0,
        description="Daily loss limit in USD - stop trading after exceeding this",
        ge=0.0,
    )

    # ===== EXECUTION CONFIGURATION =====
    execution_interval_seconds: int = Field(
        default=180,
        description="How often to execute trading decisions (seconds)",
        gt=0,
    )

    # ===== ASSETS CONFIGURATION =====
    trading_assets: str = Field(
        default="BTC/USD:USD,ETH/USD:USD,SOL/USD:USD",
        description="Comma-separated list of trading pairs"
    )

    # ===== LOGGING CONFIGURATION =====
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_dir: str = Field(
        default="./logs",
        description="Directory for log files"
    )

    # ===== HYPERLIQUID URL =====
    hyperliquid_testnet: bool = Field(
        default=False,
        description="Use Hyperliquid testnet instead of mainnet"
    )

    # ===== MOTHERHAVEN INTEGRATION =====
    motherhaven_enabled: bool = Field(
        default=False,
        description="Enable logging to Motherhaven dashboard"
    )
    motherhaven_api_url: str = Field(
        default="https://motherhaven.app",
        description="Base URL of Motherhaven Next.js API (production: https://motherhaven.app, dev: http://localhost:3000)"
    )
    motherhaven_api_key: str = Field(
        default="",
        description="API key for Motherhaven ingest endpoints (x-api-key header)"
    )
    motherhaven_timeout: int = Field(
        default=10,
        description="Request timeout for Motherhaven API calls (seconds)",
        gt=0,
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {v}")
        return v.upper()

    @field_validator("trading_assets", mode="before")
    @classmethod
    def validate_trading_assets(cls, v):
        """Validate trading assets string."""
        if isinstance(v, list):
            v = ",".join(v)

        assets = [asset.strip() for asset in v.split(",")]

        if not assets:
            raise ValueError("trading_assets cannot be empty")

        if len(assets) > 10:
            raise ValueError("trading_assets exceeds maximum of 10 assets")

        # Return as comma-separated string to match field type
        return ",".join(assets)

    def get_trading_assets(self) -> list[str]:
        """Get list of trading assets."""
        if isinstance(self.trading_assets, str):
            return [asset.strip() for asset in self.trading_assets.split(",")]
        return self.trading_assets

    def is_live_trading(self) -> bool:
        """Check if in live trading mode."""
        return self.trading_mode == TradingMode.LIVE

    def is_paper_trading(self) -> bool:
        """Check if in paper trading mode."""
        return self.trading_mode == TradingMode.PAPER

    def get_hyperliquid_url(self) -> str:
        """Get Hyperliquid API URL based on mode."""
        if self.hyperliquid_testnet:
            return "https://testnet.hyperliquid.com"
        return "https://api.hyperliquid.com"

    def get_log_path(self) -> Path:
        """Get log directory path, creating if needed."""
        log_path = Path(self.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path

    def validate_api_keys(self) -> tuple[bool, list[str]]:
        """
        Validate that required API keys are configured.

        Returns:
            (is_valid, list_of_missing_keys)
        """
        missing_keys = []

        if not self.anthropic_api_key:
            missing_keys.append("ANTHROPIC_API_KEY")

        if self.is_live_trading():
            if not self.hyperliquid_wallet_private_key:
                missing_keys.append("HYPERLIQUID_WALLET_PRIVATE_KEY")

        return len(missing_keys) == 0, missing_keys

    def validate_motherhaven_config(self) -> tuple[bool, list[str]]:
        """
        Validate that Motherhaven integration is properly configured.

        Returns:
            (is_valid, list_of_issues)
        """
        if not self.motherhaven_enabled:
            return True, []  # Not enabled, so no validation needed

        issues = []

        if not self.motherhaven_api_url:
            issues.append("MOTHERHAVEN_API_URL must be set when Motherhaven is enabled")

        if not self.motherhaven_api_key:
            issues.append("MOTHERHAVEN_API_KEY must be set when Motherhaven is enabled")

        return len(issues) == 0, issues


# Create singleton instance of settings
# This is imported and used throughout the application
settings = Settings()


# Convenience functions for common access patterns
def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def is_live_trading() -> bool:
    """Check if currently in live trading mode."""
    return settings.is_live_trading()


def is_paper_trading() -> bool:
    """Check if currently in paper trading mode."""
    return settings.is_paper_trading()


if __name__ == "__main__":
    # Test the settings when run directly
    print("=" * 60)
    print("Configuration Settings")
    print("=" * 60)
    print()
    print(f"Trading Mode: {settings.trading_mode.value}")
    print(f"Is Live: {settings.is_live_trading()}")
    print(f"Is Paper: {settings.is_paper_trading()}")
    print()
    print("Position Management:")
    print(f"  Max Position Size: ${settings.max_position_size_usd:,.2f}")
    print(f"  Max Leverage: {settings.max_leverage}x")
    print(f"  Daily Loss Limit: ${settings.daily_loss_limit_usd:,.2f}")
    print()
    print("Execution:")
    print(f"  Interval: {settings.execution_interval_seconds} seconds")
    print(f"  Trading Assets: {settings.get_trading_assets()}")
    print()
    print("Logging:")
    print(f"  Log Level: {settings.log_level}")
    print(f"  Log Directory: {settings.log_dir}")
    print()

    # Validate API keys
    is_valid, missing = settings.validate_api_keys()
    print("API Key Status:")
    if is_valid:
        print("  [OK] All required API keys configured")
    else:
        print(f"  [WARNING] Missing API keys: {', '.join(missing)}")
    print()
    print("=" * 60)
