# Project Plan - Alpha Arena Mini

**Strategy**: Build incrementally, test extensively, scale carefully
**Timeline**: 4-6 weeks to live trading
**Risk Level**: 🟡 Medium (real money involved, but starting small)

---

## 📋 Phase 1: Data Pipeline (Week 1)

**Goal**: Fetch and process market data reliably

### Task 1.1: Project Setup
**Duration**: 30 minutes
**Risk**: 🟢 None

**Files to Create**:
```bash
alpha-arena-mini/
├── .env.example          # Template for API keys
├── .gitignore           # Ignore logs, env files, cache
├── requirements.txt     # Python dependencies
└── config/
    ├── __init__.py
    └── settings.py      # Configuration management
```

**Checklist**:
- [ ] Create directory structure
- [ ] Initialize git repository
- [ ] Create virtual environment
- [ ] Add `.gitignore` for Python projects
- [ ] Create `.env.example` with placeholders

**.env.example Template**:
```bash
# Exchange API (Hyperliquid)
HYPERLIQUID_API_KEY=your_api_key_here
HYPERLIQUID_SECRET=your_secret_here

# LLM APIs
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here

# Trading Configuration
TRADING_MODE=paper  # paper or live
MAX_POSITION_SIZE_USD=50
MAX_LEVERAGE=5
DAILY_LOSS_LIMIT_USD=20

# Logging
LOG_LEVEL=INFO
LOG_DIR=./logs
```

**Verification**:
```bash
# Verify structure
tree alpha-arena-mini

# Should show all directories created
```

---

### Task 1.2: Install Dependencies
**Duration**: 30 minutes
**Risk**: 🟢 Low

**requirements.txt**:
```txt
# Exchange & Market Data
ccxt>=4.0.0
requests>=2.31.0

# Data Processing
pandas>=2.0.0
numpy>=1.24.0

# Technical Indicators
ta-lib>=0.4.28  # May need system install
pandas-ta>=0.3.14b  # Pure Python alternative

# LLM APIs
anthropic>=0.25.0
openai>=1.0.0

# Utilities
python-dotenv>=1.0.0
pydantic>=2.0.0  # For data validation
tenacity>=8.2.0  # For retries

# Database/Storage (optional, start with SQLite)
# redis>=5.0.0  # For caching (optional)

# Async (for future optimization)
aiohttp>=3.9.0
asyncio>=3.4.3

# Logging & Monitoring
coloredlogs>=15.0
```

**Checklist**:
- [ ] Create `requirements.txt`
- [ ] Create Python virtual environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Test imports work

**Special Notes**:
- `ta-lib` may require system installation first:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install ta-lib
  
  # macOS
  brew install ta-lib
  
  # Windows: Download from https://github.com/mrjbq7/ta-lib
  ```
- If `ta-lib` fails, use `pandas-ta` instead (pure Python, easier)

---

### Task 1.3: Configuration System
**Duration**: 1-2 hours
**Risk**: 🟢 Low

**File**: `config/settings.py`

```python
"""
Configuration management using environment variables and Pydantic
"""
import os
from enum import Enum
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

class Settings(BaseSettings):
    """Global application settings"""
    
    # Exchange
    hyperliquid_api_key: str = Field(default="", env="HYPERLIQUID_API_KEY")
    hyperliquid_secret: str = Field(default="", env="HYPERLIQUID_SECRET")
    
    # LLM APIs
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    
    # Trading
    trading_mode: TradingMode = Field(default=TradingMode.PAPER, env="TRADING_MODE")
    max_position_size_usd: float = Field(default=50.0, env="MAX_POSITION_SIZE_USD")
    max_leverage: int = Field(default=5, env="MAX_LEVERAGE")
    daily_loss_limit_usd: float = Field(default=20.0, env="DAILY_LOSS_LIMIT_USD")
    
    # Execution
    execution_interval_seconds: int = Field(default=180, env="EXECUTION_INTERVAL")  # 3 min
    
    # Assets
    trading_assets: list[str] = Field(default=["BTC/USD:USD", "ETH/USD:USD", "SOL/USD:USD"])
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_dir: str = Field(default="./logs", env="LOG_DIR")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton instance
settings = Settings()
```

**Checklist**:
- [ ] Create `config/settings.py`
- [ ] Create `.env` file from `.env.example`
- [ ] Test settings load: `from config.settings import settings`
- [ ] Verify environment variables work

**Testing**:
```python
# test_config.py
from config.settings import settings, TradingMode

print(f"Trading Mode: {settings.trading_mode}")
print(f"Max Position: ${settings.max_position_size_usd}")
print(f"Assets: {settings.trading_assets}")

assert settings.trading_mode == TradingMode.PAPER  # Start in paper mode!
```

---

### Task 1.4: Market Data Fetcher
**Duration**: 2-3 hours
**Risk**: 🟡 Medium (API connectivity)

**File**: `data/fetcher.py`

```python
"""
Market data fetching from Hyperliquid via ccxt
"""
import ccxt
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from config.settings import settings

class MarketDataFetcher:
    """Fetch market data from Hyperliquid exchange"""
    
    def __init__(self):
        """Initialize exchange connection"""
        self.exchange = ccxt.hyperliquid({
            'apiKey': settings.hyperliquid_api_key,
            'secret': settings.hyperliquid_secret,
            'enableRateLimit': True,
        })
        
    def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch current ticker (price, volume, etc.)"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume': ticker['quoteVolume'],
                'timestamp': datetime.now(),
            }
        except Exception as e:
            print(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '3m', limit: int = 100) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USD:USD')
            timeframe: Candlestick interval ('1m', '3m', '5m', '1h', '4h', etc.)
            limit: Number of candles to fetch
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_all_tickers(self) -> Dict[str, Dict]:
        """Fetch tickers for all configured assets"""
        tickers = {}
        for symbol in settings.trading_assets:
            ticker = self.fetch_ticker(symbol)
            if ticker:
                tickers[symbol] = ticker
        return tickers

# Example usage
if __name__ == "__main__":
    fetcher = MarketDataFetcher()
    
    # Test single ticker
    btc_ticker = fetcher.fetch_ticker('BTC/USD:USD')
    print(f"BTC Price: ${btc_ticker['price']:,.2f}")
    
    # Test OHLCV data
    btc_ohlcv = fetcher.fetch_ohlcv('BTC/USD:USD', timeframe='3m', limit=10)
    print(f"\nLatest 10 3-minute candles:")
    print(btc_ohlcv)
```

**Checklist**:
- [ ] Create `data/fetcher.py`
- [ ] Test ticker fetching
- [ ] Test OHLCV fetching
- [ ] Verify all 3 assets work (BTC, ETH, SOL)
- [ ] Handle API errors gracefully

**Verification**:
```bash
python data/fetcher.py

# Should output:
# BTC Price: $37,245.50
# Latest 10 3-minute candles: [DataFrame]
```

---

### Task 1.5: Technical Indicators
**Duration**: 2-3 hours
**Risk**: 🟢 Low (pure calculation)

**File**: `data/indicators.py`

```python
"""
Calculate technical indicators (RSI, MACD, EMA)
"""
import pandas as pd
import pandas_ta as ta  # Using pandas_ta for easier setup

class TechnicalIndicators:
    """Calculate various technical indicators"""
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Exponential Moving Average"""
        return ta.ema(df['close'], length=period)
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        return ta.rsi(df['close'], length=period)
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
        """
        MACD (Moving Average Convergence Divergence)
        Returns: DataFrame with MACD, signal, histogram
        """
        macd = ta.macd(df['close'])
        return macd
    
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators and add to DataFrame"""
        df = df.copy()
        
        # EMA (20 and 50 period)
        df['ema_20'] = TechnicalIndicators.calculate_ema(df, period=20)
        df['ema_50'] = TechnicalIndicators.calculate_ema(df, period=50)
        
        # RSI (7 and 14 period, like Alpha Arena)
        df['rsi_7'] = TechnicalIndicators.calculate_rsi(df, period=7)
        df['rsi_14'] = TechnicalIndicators.calculate_rsi(df, period=14)
        
        # MACD
        macd_df = TechnicalIndicators.calculate_macd(df)
        if macd_df is not None:
            df['macd'] = macd_df['MACD_12_26_9']
            df['macd_signal'] = macd_df['MACDs_12_26_9']
            df['macd_hist'] = macd_df['MACDh_12_26_9']
        
        return df

# Example usage
if __name__ == "__main__":
    from data.fetcher import MarketDataFetcher
    
    fetcher = MarketDataFetcher()
    df = fetcher.fetch_ohlcv('BTC/USD:USD', timeframe='3m', limit=100)
    
    # Calculate indicators
    df = TechnicalIndicators.calculate_all(df)
    
    print("Latest data with indicators:")
    print(df.tail())
    
    # Show latest values
    latest = df.iloc[-1]
    print(f"\nBTC Latest Indicators:")
    print(f"Price: ${latest['close']:,.2f}")
    print(f"EMA-20: ${latest['ema_20']:,.2f}")
    print(f"RSI-7: {latest['rsi_7']:.2f}")
    print(f"RSI-14: {latest['rsi_14']:.2f}")
    print(f"MACD: {latest['macd']:.2f}")
```

**Checklist**:
- [ ] Create `data/indicators.py`
- [ ] Test EMA calculation
- [ ] Test RSI calculation
- [ ] Test MACD calculation
- [ ] Verify output matches expected format
- [ ] Test with real BTC data

**Verification**:
```bash
python data/indicators.py

# Should output technical indicators matching market conditions
```

---

### Phase 1 Completion Criteria

- ✅ Project structure created
- ✅ Dependencies installed
- ✅ Configuration system working
- ✅ Can fetch market data from Hyperliquid
- ✅ Can calculate technical indicators
- ✅ Data updates every 1-3 minutes
- ✅ No errors in data pipeline

**Commit**: `feat(phase1): complete data pipeline with market data and indicators`

---

## 📋 Phase 2: LLM Integration (Week 1-2)

**Goal**: Get LLM making trade decisions from market data

### Task 2.1: Prompt Engineering
**Duration**: 2-3 hours
**Risk**: 🟡 Medium (critical for quality decisions)

**File**: `llm/prompts.py`

Based on Alpha Arena's prompt structure, create templates that:
1. Provide market context (prices, indicators, trends)
2. Show account state (cash, positions, PnL)
3. Set clear rules (position sizing, leverage limits)
4. Request structured output (JSON format)

**Key sections**:
- System prompt (role, objectives, constraints)
- Market data formatting
- Technical indicators formatting
- Account state formatting
- Output format specification

---

### Task 2.2: LLM Client
**Duration**: 2-3 hours
**Risk**: 🟡 Medium

**File**: `llm/client.py`

Implement API clients for:
- Claude (Anthropic API)
- GPT-4 (OpenAI API)

Features:
- Retry logic with exponential backoff
- Error handling
- Response validation
- Rate limit handling

---

### Task 2.3: Response Parser
**Duration**: 1-2 hours
**Risk**: 🟢 Low

**File**: `llm/parser.py`

Parse LLM JSON responses into structured trade decisions:
- Validate JSON format
- Extract: coin, signal (buy/sell/hold), quantity, leverage
- Extract: confidence, justification, exit plan
- Handle malformed responses gracefully

---

### Phase 2 Completion Criteria

- ✅ Prompt template working
- ✅ LLM returns valid trade decisions
- ✅ JSON parsing robust
- ✅ Can handle API errors
- ✅ Test runs for 1 hour without crashes

**Commit**: `feat(phase2): integrate LLM decision making with Claude/GPT`

---

## 📋 Phase 3: Paper Trading (Week 2-3)

**Goal**: Simulate trading to test logic without real money

### Task 3.1: Paper Trading Simulator
**Duration**: 3-4 hours
**Risk**: 🟢 Low

**File**: `trading/simulator.py`

Simulate:
- Order execution (instant fills at market price)
- Position tracking (qty, entry price, PnL)
- Account balance updates
- Fees (0.02% taker, like Hyperliquid)

---

### Task 3.2: Position Management
**Duration**: 2-3 hours
**Risk**: 🟡 Medium

**File**: `trading/position.py`

Track:
- Open positions (symbol, qty, entry, current PnL)
- Position history
- Exit conditions (TP, SL, invalidation)

---

### Task 3.3: Risk Checks
**Duration**: 2-3 hours
**Risk**: 🔴 Critical

**File**: `trading/risk.py`

Implement safety checks:
- Max position size
- Max leverage
- Daily loss limit
- Portfolio exposure limits

**MUST block trades that violate rules**

---

### Phase 3 Completion Criteria

- ✅ Paper trading works
- ✅ Can run autonomously for 3-7 days
- ✅ Positions tracked correctly
- ✅ PnL calculated accurately
- ✅ Risk controls tested
- ✅ No crashes or data loss

**Commit**: `feat(phase3): complete paper trading simulator with risk controls`

---

## 📋 Phase 4: Live Trading Prep (Week 3-4)

**Goal**: Get ready for real money

### Task 4.1: Hyperliquid Execution
**Duration**: 3-4 hours
**Risk**: 🔴 High

**File**: `trading/executor.py`

Implement real order execution:
- Market orders
- Position opening/closing
- Error handling
- Order confirmation

---

### Task 4.2: Emergency Controls
**Duration**: 2-3 hours
**Risk**: 🔴 Critical

Add:
- Manual stop button (stops all trading)
- Close all positions function
- Pause trading function

---

### Task 4.3: Monitoring
**Duration**: 2-3 hours
**Risk**: 🟡 Medium

Create:
- Real-time logging
- Performance dashboard (optional CLI)
- Error alerts
- Position monitoring

---

### Phase 4 Completion Criteria

- ✅ Can execute real orders
- ✅ Emergency stop works
- ✅ Can close all positions manually
- ✅ Monitoring functional
- ✅ Ready for $100 test

**Commit**: `feat(phase4): implement live trading execution with emergency controls`

---

## 📋 Phase 5: Live Trading (Week 4+)

**Goal**: Trade with real capital (start tiny!)

### Task 5.1: First Live Run
**Duration**: Ongoing
**Risk**: 🔴 High

**Start Conditions**:
- Capital: $100-200
- Max position: $30
- Max leverage: 3x
- Daily loss limit: $15
- Monitor: Every 2-4 hours

**Run for 1 week minimum**

---

### Task 5.2: Data Collection
**Duration**: Ongoing
**Risk**: 🟢 Low

Log everything:
- All LLM prompts and responses
- All trades and fills
- All account states
- All errors

---

### Phase 5 Completion Criteria

- ✅ Trades live for 1 week
- ✅ No catastrophic losses
- ✅ Data collected
- ✅ Bot stable
- ✅ Ready to analyze results

**Commit**: `feat(phase5): complete first week of live trading`

---

## 📋 Phase 6: Multi-Model (Week 5+)

**Goal**: Compare different LLMs

### Task 6.1: Add Second Model
**Duration**: 2-3 hours
**Risk**: 🟡 Medium

Add GPT-4 agent running in parallel

---

### Task 6.2: Comparative Analysis
**Duration**: Ongoing
**Risk**: 🟢 Low

Compare:
- PnL and Sharpe ratio
- Risk appetite
- Trade frequency
- Holding periods
- Directional bias

---

### Phase 6 Completion Criteria

- ✅ 2 models running
- ✅ 2 weeks of data collected
- ✅ Analysis complete
- ✅ Report written

---

## 📊 Progress Tracking

| Phase | Status | Start Date | End Date | Notes |
|-------|--------|------------|----------|-------|
| Phase 1: Data | 🟡 In Progress | 2024-11-13 | TBD | Starting now |
| Phase 2: LLM | ⏳ Not Started | TBD | TBD | |
| Phase 3: Paper Trading | ⏳ Not Started | TBD | TBD | |
| Phase 4: Live Prep | ⏳ Not Started | TBD | TBD | |
| Phase 5: Live Trading | ⏳ Not Started | TBD | TBD | |
| Phase 6: Multi-Model | ⏳ Not Started | TBD | TBD | Optional |

---

**Next Step**: Start Phase 1, Task 1.1 → Project Setup →
