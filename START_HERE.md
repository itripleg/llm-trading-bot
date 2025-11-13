# 🚀 START HERE - Alpha Arena Mini

**Created**: 2024-11-13
**Status**: 🟡 PLANNING - Initial Setup Phase
**Language**: Python 3.10+

## ⚡ Quick Start for New Agents/Developers

### 1️⃣ First, Read These Files (in order):
1. **THIS FILE** - Overview and entry point
2. `PROJECT_PLAN.md` - Phased implementation strategy
3. `CHANGELOG.md` - Track all changes (update as you go)
4. `../README.md` - Project overview

### 2️⃣ What Is This Project?

We're building a **smaller-scale replication** of Nof1's Alpha Arena - an experiment where LLMs trade cryptocurrency autonomously with real capital. Think of it as:

- **LLM-powered trading bot** that makes decisions based on market data
- **Comparative study** of how different LLMs (Claude, GPT) behave as traders
- **Live experiment** with real money (but starting very small)
- **Research project** to understand LLM decision-making under uncertainty

### 3️⃣ Core Concept

```
Every 2-5 minutes:
1. Fetch market data (prices, indicators, account state)
2. Format as prompt for LLM
3. LLM analyzes and decides: buy/sell/hold
4. Execute trade on Hyperliquid exchange
5. Log everything for analysis
6. Repeat
```

**Key Insight from Alpha Arena**: LLMs show consistent behavioral patterns:
- Risk appetite (position sizing)
- Directional bias (long vs short preference)
- Holding periods (how long they keep positions)
- Trade frequency (active vs passive)
- Confidence levels (self-reported)

### 4️⃣ Development Philosophy

**Build in Phases**:
1. ✅ Planning & Structure (you are here)
2. 🔄 Data Pipeline (get market data working)
3. ⏳ LLM Integration (get Claude responding)
4. ⏳ Paper Trading (simulate without real money)
5. ⏳ Live Trading (start with $100-200)
6. ⏳ Multi-Model Comparison

**Principles**:
- Start simple, add complexity gradually
- Paper trade extensively before going live
- Log everything for debugging and analysis
- Test with tiny amounts of real capital first
- Safety checks at every step

### 5️⃣ Project Structure

```
alpha-arena-mini/
├── .progress/              ← Documentation & tracking
│   ├── START_HERE.md      ← You are here
│   ├── PROJECT_PLAN.md    ← Implementation phases
│   └── CHANGELOG.md       ← Change tracking
│
├── config/                 ← Settings & configuration
│   ├── settings.py        ← Global config, API keys
│   └── trading_rules.py   ← Risk limits, position sizing
│
├── data/                   ← Market data layer
│   ├── fetcher.py         ← Get data from Hyperliquid
│   ├── indicators.py      ← Calculate RSI, MACD, EMA
│   └── storage.py         ← Historical data storage
│
├── llm/                    ← LLM integration
│   ├── client.py          ← API wrapper (Claude, GPT)
│   ├── prompts.py         ← Prompt templates
│   └── parser.py          ← Parse LLM JSON responses
│
├── trading/                ← Execution layer
│   ├── executor.py        ← Place orders
│   ├── position.py        ← Track positions
│   ├── risk.py            ← Risk checks
│   └── account.py         ← Account state
│
├── agents/                 ← Agent implementations
│   ├── base_agent.py      ← Base class
│   ├── claude_agent.py    ← Claude-specific
│   └── gpt_agent.py       ← GPT-specific
│
├── orchestrator/           ← Coordination
│   ├── harness.py         ← Main trading loop
│   └── scheduler.py       ← Timing control
│
├── analysis/               ← Performance tracking
│   ├── metrics.py         ← Sharpe, PnL, etc.
│   └── reporting.py       ← Generate reports
│
├── logs/                   ← Logs directory
└── main.py                 ← Entry point
```

### 6️⃣ Key Design Decisions

**Why Hyperliquid?**
- 24/7 crypto markets (continuous testing)
- Easy API integration
- Transparent on-chain data
- Low fees
- Same platform as original Alpha Arena

**Why Python?**
- Best libraries for trading (ccxt, pandas, ta-lib)
- Excellent LLM SDK support (anthropic, openai)
- Easy data processing
- Quick prototyping

**Why These Components?**
- **Modular design** - Easy to test each piece independently
- **Separation of concerns** - Data, LLM, Trading are isolated
- **Swappable** - Can easily add new LLMs or exchanges
- **Testable** - Mock any component for testing

### 7️⃣ Safety First

Before any live trading:

1. **Paper Trading Phase** (1-2 weeks minimum)
   - Simulate trades without real money
   - Test all LLM responses
   - Verify risk controls work
   - Log all decisions

2. **Tiny Capital Test** ($100-200)
   - Very small positions
   - Low leverage (2-3x max)
   - Monitor constantly
   - Can afford to lose it all

3. **Risk Controls**
   - Maximum position size (e.g., $50)
   - Maximum daily loss (e.g., $20)
   - Stop losses on every trade
   - Manual kill switch

4. **Monitoring**
   - Real-time logs
   - Performance dashboards
   - Error alerts
   - Regular check-ins

## 📋 Implementation Phases

### Phase 1: Foundation (Week 1) ← **START HERE**
**Goal**: Get basic data flowing

**Tasks**:
- [x] Create project structure
- [x] Define file structure
- [ ] Set up configuration (API keys, settings)
- [ ] Implement market data fetcher (Hyperliquid)
- [ ] Calculate basic indicators (RSI, MACD, EMA)
- [ ] Test data pipeline independently

**Success Criteria**:
- Can fetch BTC/ETH/SOL prices
- Can calculate technical indicators
- Data updates every 1-5 minutes
- No errors in data fetching

---

### Phase 2: LLM Integration (Week 1-2)
**Goal**: Get Claude making trading decisions

**Tasks**:
- [ ] Create prompt template (based on Alpha Arena format)
- [ ] Implement Claude API client
- [ ] Parse JSON responses from LLM
- [ ] Test prompt with real market data
- [ ] Validate LLM output format

**Success Criteria**:
- Claude returns valid trade decisions
- JSON parsing works reliably
- Responses include: coin, direction, size, confidence
- Can handle errors gracefully

---

### Phase 3: Paper Trading (Week 2-3)
**Goal**: Simulate trading without real money

**Tasks**:
- [ ] Build paper trading simulator
- [ ] Track fake positions
- [ ] Calculate fake PnL
- [ ] Run for 3-7 days continuously
- [ ] Log all decisions

**Success Criteria**:
- Bot runs autonomously for days
- Positions tracked correctly
- PnL calculated accurately
- No crashes or hangs

---

### Phase 4: Live Trading Prep (Week 3-4)
**Goal**: Get ready for real capital

**Tasks**:
- [ ] Implement Hyperliquid order execution
- [ ] Add risk checks (position size, leverage)
- [ ] Create emergency stop mechanism
- [ ] Set up monitoring/alerts
- [ ] Test with $100 on testnet (if available)

**Success Criteria**:
- Can place real orders
- Risk controls block bad trades
- Can manually stop bot
- Alerts work

---

### Phase 5: Live Trading (Week 4+)
**Goal**: Trade with real money (carefully!)

**Tasks**:
- [ ] Start with $100-200 capital
- [ ] Run for 1 week minimum
- [ ] Monitor constantly
- [ ] Log all behavior
- [ ] Analyze results

**Success Criteria**:
- Bot trades live successfully
- No major losses
- Collects useful data
- Ready to scale if successful

---

### Phase 6: Multi-Model Comparison (Week 5+)
**Goal**: Compare different LLMs

**Tasks**:
- [ ] Add GPT-4 agent
- [ ] Run both simultaneously
- [ ] Compare behavioral patterns
- [ ] Analyze differences
- [ ] Generate report

**Success Criteria**:
- Both models running
- Clear behavioral differences observed
- Data for comparison collected
- Insights documented

## 🎯 Current Focus

**We're in Phase 1: Foundation**

**Immediate Next Steps**:
1. Create `config/settings.py` with API key placeholders
2. Build `data/fetcher.py` to get market data from Hyperliquid
3. Implement `data/indicators.py` for technical analysis
4. Test data pipeline works

**What NOT to do yet**:
- Don't implement trading execution
- Don't connect to LLM APIs yet
- Don't worry about UI/dashboards
- Focus on: Can we get clean market data?

## 🔗 Useful Resources

**Alpha Arena Reference**:
- Original concept document (in project context)
- Key features to replicate:
  - Market data input format
  - Prompt structure
  - Decision output format
  - Risk management approach

**Technical Documentation**:
- Hyperliquid API: https://hyperliquid.gitbook.io/
- ccxt Library: https://docs.ccxt.com/
- Anthropic API: https://docs.anthropic.com/
- TA-Lib: https://mrjbq7.github.io/ta-lib/

**Python Libraries**:
- `ccxt` - Exchange connectivity
- `pandas` - Data manipulation
- `ta-lib` or `pandas-ta` - Technical indicators
- `anthropic` - Claude API
- `openai` - GPT API
- `python-dotenv` - Environment variables

## 📝 Work Protocol

**For Every Session**:
1. Update `CHANGELOG.md` with what you're doing
2. Commit at logical checkpoints
3. Test each component independently
4. Update this file if project structure changes
5. Document any issues or learnings

**Git Commits**:
- Use clear commit messages
- Format: `feat(phase1): implement market data fetcher`
- Commit frequently (every 30-60 min of work)

**Testing**:
- Test each module independently first
- Use print statements liberally for debugging
- Save test outputs to logs/
- Don't move to next phase until current one works

## ⚠️ Important Reminders

1. **This is real money** - Even $100 can be lost
2. **LLMs make mistakes** - They're not perfect traders
3. **Start small** - Paper trade extensively first
4. **Log everything** - You'll need it for debugging
5. **Have kill switches** - Be able to stop immediately
6. **Monitor actively** - Don't leave it running unattended initially

## 🎓 Learning Goals

Beyond just building a bot, we want to learn:

1. **How do LLMs behave as traders?**
   - Risk-seeking or risk-averse?
   - Momentum or mean-reversion strategies?
   - Quick exits or long holds?

2. **What are the failure modes?**
   - Misreading data?
   - Over-trading?
   - Ignoring stop losses?
   - Rule-gaming?

3. **How do different models compare?**
   - Claude vs GPT behavioral differences
   - Confidence calibration
   - Explanation quality

4. **What makes a good trading prompt?**
   - How much context?
   - What instructions?
   - How to handle edge cases?

---

**Ready to start building?** → Read `PROJECT_PLAN.md` for detailed tasks →

**Questions?** → Update this file with clarifications as you learn →
