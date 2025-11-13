# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Alpha Arena Mini** is a Python-based LLM trading bot that executes trades on Hyperliquid based on Claude's analysis of market data. The bot runs a continuous loop: every 2-3 minutes it fetches market data, calculates technical indicators, sends them to Claude via a carefully crafted prompt, receives structured trade decisions, and executes them on Hyperliquid. Multiple instances can be deployed using different API keys to test different LLMs or strategies.

Key specs:
- **Language**: Python 3.10+
- **Exchange**: Hyperliquid (via ccxt library)
- **Primary LLM**: Anthropic Claude
- **Capital**: Starting small ($100-$200) after paper trading validation
- **Assets**: BTC/USD:USD, ETH/USD:USD, SOL/USD:USD (configurable)
- **Leverage**: Max 5x initially
- **Execution Frequency**: Every 2-3 minutes
- **Basis**: Replicates Nof1's Alpha Arena design (see blogpost.txt)

## Core Architecture

```
alpha-arena-mini/
├── .progress/              # Documentation and phase tracking
│   ├── START_HERE.md      # Entry point - read first
│   ├── PROJECT_PLAN.md    # Detailed phase-by-phase tasks
│   ├── CHANGELOG.md       # Track all changes
│   └── PROMPT.md          # AI agent context
│
├── config/                 # Configuration management
│   └── settings.py        # Pydantic-based settings, env var loading
│
├── data/                   # Market data layer
│   ├── fetcher.py         # Hyperliquid API integration via ccxt
│   ├── indicators.py      # Technical indicators (EMA, RSI, MACD, ATR)
│   └── storage.py         # Optional historical data persistence
│
├── llm/                    # LLM integration
│   ├── client.py          # Anthropic Claude API client
│   ├── prompts.py         # Prompt templates for trading decisions
│   └── parser.py          # Parse and validate Claude JSON responses
│
├── trading/                # Execution and risk management
│   ├── executor.py        # Order placement on Hyperliquid
│   ├── position.py        # Position tracking and management
│   ├── risk.py            # Risk checks (position size, leverage, daily loss)
│   ├── simulator.py       # Paper trading simulator
│   └── account.py         # Account state management
│
├── orchestrator/           # Main bot orchestration
│   ├── harness.py         # Main trading loop (2-3 min cycle)
│   └── scheduler.py       # Execution timing and coordination
│
├── web/                    # Web interface for monitoring (optional)
│   ├── app.py             # Flask/FastAPI server
│   ├── routes.py          # API endpoints for dashboard
│   └── templates/         # Dashboard templates
│
├── analysis/               # Performance tracking and analysis
│   ├── metrics.py         # Sharpe ratio, PnL, statistics
│   └── reporting.py       # Report generation
│
├── logs/                   # Runtime logs and trade history
├── tests/                  # Unit and integration tests
├── blogpost.txt           # Nof1 Alpha Arena blog post (reference)
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
└── main.py                # Entry point
```

## Development Workflow

### Documentation First
- **START_HERE.md**: Comprehensive introduction. Read this before any work.
- **PROJECT_PLAN.md**: Detailed 6-phase implementation plan with specific tasks, durations, and success criteria.
- **CHANGELOG.md**: Update after every significant change (required).
- **PROMPT.md**: Context and workflow guidance.
- **blogpost.txt**: Reference Nof1's Alpha Arena design and findings.

### Phases
1. **Phase 1 (Week 1)**: Data Pipeline - Fetch market data, calculate indicators
2. **Phase 2 (Week 1-2)**: LLM Integration - Claude decision making
3. **Phase 3 (Week 2-3)**: Paper Trading - Simulate trading without real money
4. **Phase 4 (Week 3-4)**: Live Trading Prep - Implement real order execution, emergency controls
5. **Phase 5 (Week 4+)**: Live Trading - Start with $100-200
6. **Phase 6 (Week 5+)**: Analysis & Web Interface - Monitor bot, analyze behavior, scale if successful

## Common Commands

```bash
# Setup and installation
python -m venv venv
venv\Scripts\activate                    # Windows
source venv/bin/activate                 # Mac/Linux
pip install -r requirements.txt

# Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys and trading settings

# Test configuration
python test_setup.py

# Test individual modules
python data/fetcher.py                   # Test market data fetching
python data/indicators.py                # Test indicator calculations
python llm/client.py                     # Test LLM integration

# Run paper trading
python main.py --mode paper

# Run live trading (after validation)
python main.py --mode live --capital 100

# Run web interface for monitoring
python web/app.py                        # Starts dashboard on localhost:5000

# Run tests
pytest tests/
```

## Critical Safety Guidelines

These are non-negotiable:

1. **Paper trading must run 1-2 weeks minimum** before any live trading. This validates:
   - Market data fetching reliability
   - LLM response parsing accuracy
   - Risk controls enforcement
   - Position tracking correctness

2. **Start live trading with $100-200 maximum**:
   - Position limits: $30-50 per trade
   - Max leverage: 3x (not 5x)
   - Daily loss limit: $15-20
   - Monitor continuously (via web interface or logs)

3. **Emergency controls required**:
   - Manual stop button to pause trading immediately
   - Close all positions function
   - Pause trading mode
   - Kill switch in orchestrator/harness.py

4. **Risk checks** (trading/risk.py) must block trades that violate:
   - Maximum position size
   - Maximum leverage
   - Daily loss limit
   - Portfolio exposure limits

5. **Log everything**:
   - All LLM prompts and responses (exactly as sent to Claude)
   - All trade decisions and executions (with timestamps)
   - All errors and edge cases
   - Account state snapshots
   - Save to logs/ directory with timestamps for post-analysis

## Key Implementation Details

### Configuration (config/settings.py)
- Uses Pydantic v2 with pydantic_settings for validation
- Loads from .env file via python-dotenv
- Environment variables override defaults
- Provides singleton `settings` instance

### Market Data (data/fetcher.py)
- Uses ccxt library for Hyperliquid integration
- Supports fetch_ticker() and fetch_ohlcv() methods
- Returns pandas DataFrames for time series data
- Handles API errors gracefully with try/except

### Technical Indicators (data/indicators.py)
- Uses pandas_ta (pure Python, no system dependencies)
- **Calculate these indicators** (based on Alpha Arena):
  - **Short timeframe (3-minute intervals)**: EMA20, EMA50, RSI (7-period), RSI (14-period), MACD
  - **Long timeframe (4-hour intervals)**: EMA20, EMA50, RSI (14-period), MACD, ATR (3 & 14 period)
  - **Additional data**: Volume (current vs average), Open Interest, Funding Rate
- Returns augmented DataFrame with all indicator columns

### LLM Integration (llm/client.py)
- Uses Anthropic API (Claude models)
- Implements retry logic with exponential backoff (tenacity library)
- Request/response validation
- Rate limit handling

### Execution Loop (orchestrator/harness.py)
- **Every 2-3 minutes:**
  1. Fetch market data for all configured assets
  2. Calculate technical indicators
  3. Get current account state (positions, cash, PnL, Sharpe ratio)
  4. Format into prompt with all market and account data
  5. Send to Claude for decision
  6. Parse and validate response
  7. Apply risk checks
  8. Execute approved trades
  9. Log everything
  10. Wait for next cycle

### Claude Prompt Structure (llm/prompts.py)
Based on Alpha Arena design, prompt must provide:
- **Market data**: Current prices, 3-min historical prices, all indicators
- **Account state**: Available cash, current positions (symbol, qty, entry price, current price, unrealized PnL, leverage)
- **Risk info**: Sharpe ratio, liquidation prices, open interest, funding rates
- **Instructions**: Position sizing rules, leverage limits, expected output format
- **Output format** (JSON):
  ```json
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
    "justification": "Technical analysis reasoning"
  }
  ```

### Paper Trading (trading/simulator.py)
- Simulates instant fills at market price
- Tracks positions with entry price and unrealized PnL
- Charges realistic fees (0.02% taker like Hyperliquid)
- Allows testing without real capital

### Risk Management (trading/risk.py)
- Validates every trade against safety limits
- Blocks violating orders before execution
- Logs all blocked trades for debugging
- Never allows emergency overrides of safety checks

### Web Interface (web/app.py - Phase 6)
Monitor bot activity via dashboard:
- Real-time account balance and PnL
- Current positions with unrealized gains/losses
- Trade history with entry/exit times and fills
- LLM response history (prompts and decisions)
- Behavioral metrics (frequency, holding periods, risk posture)
- Manual controls (pause/resume, emergency stop)
- Performance charts (PnL over time, Sharpe ratio)

## Behavioral Metrics to Track

From Alpha Arena findings, track these patterns:
- **Risk posture**: Average position size, leverage usage
- **Directional bias**: Long vs short trade ratio
- **Holding periods**: Average time from entry to exit
- **Trade frequency**: Number of trades per day/week
- **Confidence calibration**: Self-reported confidence vs actual accuracy
- **Exit plan tightness**: Stop loss / target distance as % of entry

## Multiple Instance Deployment

To run multiple instances with different configurations:

1. Create separate .env files: `.env.claude1`, `.env.claude2`, etc.
2. Run instances with different environment files:
   ```bash
   # Terminal 1
   DOTENV_FILE=.env.claude1 python main.py --mode paper

   # Terminal 2
   DOTENV_FILE=.env.claude2 python main.py --mode paper
   ```
3. Each instance maintains separate logs and position tracking
4. Ensure different API keys and account configurations
5. Web interface can aggregate data from all instances

## Testing Strategy

- **Unit tests**: Test each module independently
- **Integration tests**: Test component interactions (data → indicators → prompt → parsing)
- **Paper trading**: Multi-day stress test before live (minimum 1 week)
- **Manual testing**: Test with small real amounts first ($10-50)
- **Logging**: Extensive logging for debugging and post-trade analysis

Run tests frequently, especially before phase transitions:
```bash
pytest tests/ -v
```

## Important Notes

### No ta-lib Dependency
The project uses pandas_ta instead of ta-lib (pure Python). This avoids system-level compilation issues.

### OHLCV Data Format
- Column order: timestamp, open, high, low, close, volume
- Timestamps converted to pandas datetime (milliseconds → datetime)
- All data in UTC

### Error Handling Patterns
- Never crash on API failures - log and continue
- Validate all external data before use
- Use try/except for risky operations
- Implement timeout handling for long operations
- Gracefully degrade functionality vs. hard failures
- If Claude response is malformed, reject trade and log for analysis

## Git Workflow

- Commit frequently (every 30-60 minutes of work)
- Use clear commit messages: `feat(phase1): implement market data fetcher`
- Update CHANGELOG.md with each meaningful commit
- Don't commit API keys or .env files (use .gitignore)
- Tag major phase completions: `git tag phase1-complete`

## When to Use Each Resource

- **START_HERE.md**: First read for any session, orientation
- **PROJECT_PLAN.md**: Reference for current phase and next tasks
- **PROMPT.md**: Context for understanding project goals
- **blogpost.txt**: Reference Alpha Arena design, indicators, and behavioral findings
- **CHANGELOG.md**: Track what's been done, what's next
- **Code comments**: Implementation details in modules
- **Logs/**: Runtime debugging and trade analysis

## Common Gotchas

1. **API Rate Limits**: ccxt has built-in rate limiting - don't disable it
2. **Timezone Issues**: Hyperliquid uses UTC - ensure all timestamps match
3. **Price Precision**: Use appropriate precision for cryptocurrency prices
4. **Position Sizing**: Always validate position sizes against account balance
5. **Network Timeouts**: Implement retry logic with exponential backoff
6. **JSON Parsing**: Claude responses may be malformed - validate before use
7. **Real Money**: Even small losses are real - test extensively first
8. **Ordering Bias**: Alpha Arena found models misread data order - be explicit in prompts
9. **Rule-gaming**: Ambiguous instructions can lead to unintended behavior - be precise
10. **Execution Loop Timing**: Maintain consistent 2-3 minute cycle; don't let one slow API call block others

## Success Criteria by Phase

Each phase has specific success criteria in PROJECT_PLAN.md. Key transition criteria:
- **Phase 1→2**: Data fetching works reliably for 30+ minutes
- **Phase 2→3**: Claude returns valid trade decisions 100% of time
- **Phase 3→4**: Paper trading runs 7+ days without crashes
- **Phase 4→5**: All emergency controls tested and working
- **Phase 5+**: Monitor for 1 week before scaling capital
- **Phase 6**: Web interface shows all relevant metrics; multiple instances deployable

---

**For new work**: Start by reading `.progress/START_HERE.md`, then reference `PROJECT_PLAN.md` for your current phase.

**Reference**: See `blogpost.txt` for Alpha Arena technical design, data format, and behavioral findings.
