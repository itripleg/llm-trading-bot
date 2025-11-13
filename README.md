# Alpha Arena Mini - LLM Trading Bot Experiment

**Smaller-scale replication of Nof1's Alpha Arena project**

## Overview

This project replicates the core concepts from [Nof1's Alpha Arena](https://nof1.ai) - testing LLMs as autonomous trading agents in live cryptocurrency markets. We're starting small with reduced capital, fewer models, and a simplified setup to validate the approach before scaling.

## Project Goals

1. **Test LLM decision-making** in real financial markets with real capital
2. **Compare model behavior** across different LLMs (Claude, GPT, etc.)
3. **Measure performance** beyond simple PnL (Sharpe ratio, holding periods, risk management)
4. **Learn patterns** - risk appetite, directional bias, trade frequency, position sizing

## Scale Comparison

| Aspect | Alpha Arena (Original) | Alpha Arena Mini (Ours) |
|--------|----------------------|------------------------|
| Capital per model | $10,000 | $500-$1,000 |
| Models tested | 6 (GPT-5, Claude, Gemini, etc.) | 1-2 initially |
| Assets | 6 coins (BTC, ETH, SOL, BNB, DOGE, XRP) | 3 coins (BTC, ETH, SOL) |
| Leverage | Up to 20x | Max 5x initially |
| Duration | ~1 month | 2-week pilot |
| Platform | Hyperliquid | Hyperliquid (same) |

## Architecture

```
alpha-arena-mini/
├── config/           # Settings, API keys, trading rules
├── data/             # Market data fetching & indicators
├── llm/              # LLM client, prompts, response parsing
├── trading/          # Order execution, position tracking
├── agents/           # Agent implementations per model
├── orchestrator/     # Main trading loop & scheduling
├── analysis/         # Performance metrics & reporting
└── logs/             # Decision logs, trades, errors
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run in paper trading mode first
python main.py --mode paper

# After testing, run live (start small!)
python main.py --mode live --capital 100
```

## Development Status

**Phase**: Planning & Initial Setup  
**Build Status**: Not started  
**Next Step**: See `.progress/START_HERE.md`

## Key Features (Planned)

- [x] Project structure defined
- [ ] Market data pipeline (Hyperliquid API)
- [ ] Technical indicators (RSI, MACD, EMA)
- [ ] LLM client integration (Claude, GPT)
- [ ] Prompt engineering & formatting
- [ ] Paper trading simulator
- [ ] Live trading execution
- [ ] Position tracking & risk management
- [ ] Performance analytics
- [ ] Multi-model comparison

## Safety Features

- **Paper trading first** - Test without real money
- **Position limits** - Max size, max leverage controls
- **Stop losses** - Automatic exit on large losses
- **Daily loss limits** - Pause trading after threshold
- **Manual override** - Emergency stop button

## Technology Stack

- **Language**: Python 3.10+
- **Exchange**: Hyperliquid (ccxt library)
- **LLMs**: Anthropic Claude, OpenAI GPT
- **Data**: pandas, ta-lib for technical analysis
- **Caching**: In-memory (optional Redis)
- **Storage**: SQLite for logs and history

## Documentation

- **For Developers**: See `.progress/START_HERE.md`
- **Architecture Details**: See `.progress/PROJECT_PLAN.md`
- **Change Log**: See `.progress/CHANGELOG.md`

## Inspiration

Based on Nof1's Alpha Arena project:
- [Alpha Arena Website](https://nof1.ai)
- Paper: "Exploring the Limits of Large Language Models as Quant Traders"

## License

MIT (for educational/research purposes)

## Disclaimer

⚠️ **This is experimental software dealing with real money. Use at your own risk.**

- Cryptocurrency trading is highly risky
- LLMs make mistakes and can lose money
- Start with small amounts you can afford to lose
- Not financial advice
- Past performance ≠ future results

---

**Ready to start?** → Read `.progress/START_HERE.md`
