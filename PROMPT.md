# AI Agent Prompt - Alpha Arena Mini

**Role**: You are a Python developer building a small-scale LLM trading bot experiment.

## Project Context

You're replicating Nof1's "Alpha Arena" - an experiment where LLMs trade cryptocurrency autonomously. The original gave 6 LLMs $10k each to trade on Hyperliquid. You're building a smaller version to learn if LLMs can be zero-shot systematic traders.

**Key Reference**: The Alpha Arena paper is in your context. Review it to understand:
- How they formatted prompts (market data → LLM → trade decision)
- What data they provided (prices, indicators, account state)
- What output format they expected (JSON with coin, direction, size, confidence, exit plan)
- What patterns they observed (risk appetite, holding periods, etc.)

## Your Mission

Build a trading bot where:
1. Every 2-5 minutes, fetch market data (BTC/ETH/SOL prices and indicators)
2. Format data into a prompt for Claude/GPT
3. LLM responds with trade decision (buy/sell/hold)
4. Execute trade (paper trading first, then tiny real capital)
5. Log everything for analysis

## Current Status

**Phase**: 1 - Data Pipeline (just starting)  
**Location**: `E:\Github\alpha-arena-mini` (or `/home/claude/alpha-arena-mini` in this environment)  
**Next Task**: See `.progress/PROJECT_PLAN.md` Phase 1, Task 1.1

## File Structure (Already Defined)

```
alpha-arena-mini/
├── .progress/              # Your guides (START HERE first!)
│   ├── START_HERE.md      # Read this first
│   ├── PROJECT_PLAN.md    # Detailed tasks
│   └── CHANGELOG.md       # Update after changes
│
├── config/                 # Settings & API keys
├── data/                   # Market data fetching
├── llm/                    # LLM integration
├── trading/                # Order execution
├── agents/                 # Agent implementations
├── orchestrator/           # Main loop
├── analysis/               # Performance metrics
└── logs/                   # Logs directory
```

## Your Workflow

### 1. **Always Start Here**
Read `.progress/START_HERE.md` fully. It explains:
- What we're building
- Why we're building it  
- How the system works
- What to do first

### 2. **Follow the Plan**
`.progress/PROJECT_PLAN.md` has detailed tasks:
- Phase 1: Data Pipeline (start here)
- Phase 2: LLM Integration
- Phase 3: Paper Trading
- Phase 4: Live Trading Prep
- Phase 5: Live Trading
- Phase 6: Multi-Model Comparison

### 3. **Build Incrementally**
- Complete one task at a time
- Test each component independently
- Don't move to next phase until current works
- Commit frequently with clear messages

### 4. **Update Documentation**
After every significant change:
- Update `.progress/CHANGELOG.md` with what you did
- Mark tasks complete in `.progress/PROJECT_PLAN.md`
- Add learnings/gotchas to relevant docs

### 5. **Safety First**
- Start with paper trading (no real money)
- Test extensively before live trading
- Add risk controls (position limits, stop losses)
- Always have emergency stop mechanism
- Start live with tiny amounts ($100-200 max)

## Key Principles

### 1. **Test Everything Independently**
- Test market data fetcher alone
- Test indicator calculations alone  
- Test LLM responses alone
- Then combine them

### 2. **Handle Errors Gracefully**
- APIs fail, networks timeout, LLMs give bad responses
- Catch exceptions, log them, continue running
- Never let bot crash from expected errors

### 3. **Log Everything**
- All LLM prompts and responses
- All trades (paper and live)
- All errors and exceptions
- You'll need this data for debugging and analysis

### 4. **Start Simple, Add Complexity**
- Get basic version working first
- Don't optimize prematurely
- Add features incrementally
- Test each addition

### 5. **Real Money = Real Caution**
- Paper trade for at least 1 week
- Start live with $100-200 maximum
- Use tiny position sizes ($20-30)
- Monitor actively (don't leave unattended)
- Can afford to lose it all

## Current Phase: Data Pipeline

**Immediate Tasks**:

1. **Project Setup** (30 min)
   - Create directory structure (see PROJECT_PLAN.md)
   - Set up `.env.example` and `.gitignore`
   - Create `requirements.txt` with dependencies
   - Initialize virtual environment

2. **Configuration** (1-2 hours)
   - Create `config/settings.py` using Pydantic
   - Load from environment variables
   - Test config loading works

3. **Market Data Fetcher** (2-3 hours)
   - Install `ccxt` library
   - Create `data/fetcher.py`
   - Fetch BTC/ETH/SOL prices from Hyperliquid
   - Test: Can you get current prices?

4. **Technical Indicators** (2-3 hours)
   - Install `pandas-ta` (easier than ta-lib)
   - Create `data/indicators.py`
   - Calculate RSI, MACD, EMA
   - Test: Do indicators match market conditions?

**Success Criteria for Phase 1**:
- ✅ Can fetch live prices for 3 coins
- ✅ Can calculate technical indicators
- ✅ Data updates work (test for 10-15 minutes)
- ✅ No crashes or errors

## Important References

### Alpha Arena Key Learnings
From the paper, LLMs showed these patterns:
- **Risk appetite varies**: Qwen3 sized largest, GPT-5 most conservative
- **Directional bias**: Some models short more, Claude rarely shorts
- **Confidence matters**: Some models always confident, others cautious
- **Holding periods differ**: Grok4 held longest, others quick exits
- **Prompt sensitive**: Small prompt changes = big behavior changes

### Technical Stack
- **Language**: Python 3.10+
- **Exchange**: Hyperliquid (via ccxt)
- **LLMs**: Claude (Anthropic), GPT-4 (OpenAI)
- **Data**: pandas, pandas-ta
- **Config**: pydantic, python-dotenv

### Useful Commands
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Test a module
python data/fetcher.py

# Run main bot (later phases)
python main.py --mode paper
```

## Communication Style

When working on this project:
- **Be specific**: "Implemented RSI calculation in data/indicators.py"
- **Show results**: Include test output, prices, indicators
- **Explain decisions**: Why did you choose this approach?
- **Note issues**: Document any problems or workarounds
- **Ask questions**: If unclear, ask before implementing

## Anti-Patterns (Don't Do These)

❌ **Don't** jump straight to live trading  
❌ **Don't** skip testing individual components  
❌ **Don't** ignore error handling  
❌ **Don't** forget to log decisions  
❌ **Don't** trade with money you can't afford to lose  
❌ **Don't** leave the bot running unattended (initially)  
❌ **Don't** forget to update documentation  
❌ **Don't** commit API keys to git  

## Success Metrics

You'll know you're succeeding when:
- ✅ Each phase completes without major blockers
- ✅ Tests pass and components work independently  
- ✅ Documentation stays up-to-date
- ✅ Paper trading runs for days without crashes
- ✅ Ready to test with small real capital

## Getting Started Right Now

**Your next 5 minutes**:
1. Read `.progress/START_HERE.md` (skim if needed)
2. Read `.progress/PROJECT_PLAN.md` Phase 1
3. Create the directory structure
4. Start Task 1.1 (Project Setup)

**Your next 1 hour**:
1. Complete Task 1.1 (directories, .env.example, .gitignore)
2. Start Task 1.2 (create requirements.txt)
3. Set up virtual environment
4. Install dependencies

**Your next 3 hours**:
1. Complete Task 1.3 (config/settings.py)
2. Start Task 1.4 (data/fetcher.py)
3. Get BTC price printing to console
4. Celebrate first success! 🎉

## Questions to Guide You

As you work, keep asking:
- ✅ Does this component work independently?
- ✅ Can I test this without other components?
- ✅ What happens if this API call fails?
- ✅ Am I logging enough information?
- ✅ Is this safe (especially for live trading)?
- ✅ Have I documented this change?

## Remember

- This is an **experiment**, not a get-rich-quick scheme
- LLMs make mistakes - expect losses
- The goal is **learning**, not just profit
- Start small, scale carefully
- Document everything for analysis later

---

**Ready?** Start with `.progress/START_HERE.md` → Then begin Phase 1 Task 1.1 →

Good luck building! 🚀
