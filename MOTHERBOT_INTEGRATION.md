# Motherbot Integration Guide

## Overview

Motherbot is the consolidated LLM trading bot interface for Motherhaven. The Python trading bot (`llm-trading-bot` submodule) runs independently and POSTs data to the Next.js API, which stores it in Firebase. The frontend (`app/llm-bot` → will be `app/motherbot`) displays this data in real-time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Python Trading Bot                           │
│           (llm-trading-bot submodule)                        │
│                                                              │
│  • Fetches market data from Hyperliquid                     │
│  • Analyzes with Claude AI                                  │
│  • Executes trades                                          │
│  • Stores in local SQLite                                   │
│  • POSTs to Motherhaven API                                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ HTTPS POST
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           Motherhaven Next.js API                            │
│         (app/api/llm-bot/ingest/*)                          │
│                                                              │
│  POST /api/llm-bot/ingest/decision                          │
│  POST /api/llm-bot/ingest/account                           │
│  POST /api/llm-bot/ingest/position                          │
│  POST /api/llm-bot/ingest/status                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Writes to
                   ▼
           ┌───────────────┐
           │   Firebase    │
           │  Firestore    │
           └───────┬───────┘
                   │
                   │ Real-time reads
                   ▼
┌─────────────────────────────────────────────────────────────┐
│         Motherbot Dashboard (Next.js)                        │
│              (app/llm-bot)                                   │
│                                                              │
│  • Account Overview                                          │
│  • Bot Status & Controls                                    │
│  • Positions Table (Open/Closed/Errors/Config/Debug)       │
│  • Decisions Feed                                            │
│  • Execution Error Tracking ✨ NEW                          │
└─────────────────────────────────────────────────────────────┘
```

---

## New Features (Just Added)

### 1. **Execution Error Tracking** ✨

The bot now tracks whether each trading decision was successfully executed:

**Database Schema Updates** (`llm-trading-bot/web/database.py`):
- `execution_status` - `'pending'`, `'success'`, `'failed'`, or `'skipped'`
- `execution_error` - Error message from Hyperliquid API
- `execution_timestamp` - When execution was attempted

**Python Bot** (`llm-trading-bot/run_analysis_bot.py`):
- Captures execution results for ALL trade types
- Logs errors to database + bot_status table
- Updates decision record with success/failure

**Next.js Frontend** (`app/llm-bot`):
- New `ErrorsTab` component shows failed executions
- `PositionsTable` now has "Errors" tab (replaces "Failed")
- Real-time error display with full context

### 2. **Improved Debug Interface**

**Existing Debug Tab** (already working):
- Shows latest system prompt
- Shows market data user prompt
- Shows Claude's raw response
- Auto-refreshes every 10 seconds

### 3. **Database Viewer** (Local Flask Dashboard)

**Flask Dashboard** (`llm-trading-bot/web/app.py`):
- Added `/api/debug/database` endpoint
- Shows raw database entries for any table
- Select from: decisions, account_state, positions, bot_status
- Displays most recent 3-5 entries as JSON

**Access**: `http://localhost:5000` (when running `python llm-trading-bot/web/app.py`)

---

## Directory Structure

```
motherhaven/
├── llm-trading-bot/               # Python bot (submodule)
│   ├── run_analysis_bot.py        # Main bot entry point
│   ├── clear_database.py          # Clear SQLite data
│   ├── web/
│   │   ├── app.py                 # Flask dashboard (local)
│   │   ├── database.py            # SQLite operations
│   │   └── motherhaven_logger.py  # POST to Motherhaven API
│   ├── scripts/
│   │   └── show_errors.py         # View execution errors
│   └── ...
│
├── app/
│   ├── llm-bot/                   # ⚠️ Rename to app/motherbot
│   │   ├── page.tsx               # Main dashboard
│   │   ├── components/
│   │   │   ├── AccountOverview.tsx
│   │   │   ├── BotStatus.tsx
│   │   │   ├── PositionsTable.tsx # Has Errors tab now ✨
│   │   │   ├── DecisionsFeed.tsx
│   │   │   └── ErrorsTab.tsx      # ✨ NEW
│   │   ├── hooks/
│   │   │   ├── useBotAccount.ts
│   │   │   ├── useBotDecisions.ts
│   │   │   ├── useBotPositions.ts
│   │   │   ├── useBotStatus.ts
│   │   │   ├── useBotDebug.ts
│   │   │   └── useBotErrors.ts    # ✨ NEW
│   │   └── types.ts               # Updated with execution tracking
│   │
│   └── api/llm-bot/
│       ├── ingest/                # POST endpoints for bot
│       │   ├── decision/
│       │   ├── account/
│       │   ├── position/
│       │   └── status/
│       ├── decisions/             # GET endpoints for frontend
│       ├── positions/
│       ├── account/
│       └── status/
│
└── .env.local
    └── LLM_BOT_API_KEY=your-key    # Must match bot's MOTHERHAVEN_API_KEY
```

---

## Setup Instructions

### 1. **Configure Motherhaven API Key**

**In main project** (`.env.local`):
```bash
LLM_BOT_API_KEY=llm-bot-sk-7f9c3e8a2b4d1f6e9c5a8b3d7e2f4a6c
```

**In bot** (`llm-trading-bot/.env`):
```bash
MOTHERHAVEN_ENABLED=true
MOTHERHAVEN_API_URL=https://motherhaven.app  # Production (default)
# MOTHERHAVEN_API_URL=http://localhost:3000  # Development
MOTHERHAVEN_API_KEY=llm-bot-sk-7f9c3e8a2b4d1f6e9c5a8b3d7e2f4a6c
MOTHERHAVEN_TIMEOUT=10
```

### 2. **Clear Database** (Fresh Start)

```bash
cd llm-trading-bot
python clear_database.py --mode live
# Type 'yes' to confirm
```

### 3. **Start the Bot**

```bash
cd llm-trading-bot
uv run python run_analysis_bot.py
```

Watch for:
```
[Motherhaven] Integration enabled - posting to https://motherhaven.app
[Motherhaven] Successfully posted to /api/llm-bot/ingest/decision
```

### 4. **View Dashboard**

**Option A: Motherhaven Frontend** (Production)
```
https://motherhaven.app/llm-bot
```

**Option B: Local Flask Dashboard**
```bash
cd llm-trading-bot
python web/app.py
# Open: http://localhost:5000
```

---

## Using the Dashboard

### **Tabs in Positions Table:**

1. **Open** - Currently open positions
2. **Closed** - Historical closed positions with realized P&L
3. **Errors** ✨ - Failed trade executions with error messages
4. **Config** - Bot configuration (read-only for now)
5. **Debug** - Latest prompts sent to Claude

### **Errors Tab Features:**

Shows all failed trade executions with:
- ❌ Error message from Hyperliquid
- 📊 Trade details (coin, signal, size, leverage)
- 🕒 Timestamp of failure
- 💡 Decision reasoning (truncated)
- 📈 Confidence level

Example errors you might see:
```
"User has no account address set up for subaccount 0"
"Insufficient balance"
"Order size too small"
"Market is closed"
```

---

## Troubleshooting

### **Bot Not Syncing to Firebase?**

1. **Check bot logs** for `[Motherhaven]` messages:
   ```bash
   cd llm-trading-bot/logs
   cat bot_stdout.log | grep Motherhaven
   ```

2. **Test API connectivity**:
   ```bash
   cd llm-trading-bot
   python web/motherhaven_logger.py
   ```

3. **Verify API keys match**:
   ```bash
   # Bot's key
   grep MOTHERHAVEN_API_KEY llm-trading-bot/.env

   # Motherhaven's key
   grep LLM_BOT_API_KEY .env.local
   ```

### **No Errors Showing Up?**

The bot only started tracking errors after the database migration. Old decisions won't have execution status. Clear the database and run fresh:

```bash
cd llm-trading-bot
python clear_database.py --mode live
uv run python run_analysis_bot.py
```

### **Want to See Errors in Terminal?**

```bash
cd llm-trading-bot
python scripts/show_errors.py --mode live
```

---

## API Endpoints Reference

### **Ingest Endpoints** (Bot → Motherhaven)

```
POST /api/llm-bot/ingest/decision
  Body: { timestamp, coin, signal, quantity_usd, leverage, confidence, justification, ... }

POST /api/llm-bot/ingest/account
  Body: { balance_usd, equity_usd, unrealized_pnl, realized_pnl, ... }

POST /api/llm-bot/ingest/position
  Body: { position_id, coin, side, entry_price, quantity_usd, leverage, ... }

POST /api/llm-bot/ingest/status
  Body: { timestamp, status, message }
```

**Authentication**: All require `x-api-key` header matching `LLM_BOT_API_KEY`

### **Query Endpoints** (Frontend ← Motherhaven)

```
GET /api/llm-bot/decisions?limit=50
GET /api/llm-bot/positions?status=open|closed|all
GET /api/llm-bot/account
GET /api/llm-bot/status
```

---

## Next Steps

### **Recommended:**

1. **Rename `app/llm-bot` → `app/motherbot`** for clarity:
   ```bash
   # Manually rename folder (permission issues with mv command)
   # Update imports in:
   #   - app/layout.tsx (if navigation links exist)
   #   - Any other files that reference /llm-bot route
   ```

2. **Update route in Next.js**:
   - Folder rename will automatically update route to `/motherbot`
   - Update any hardcoded `/llm-bot` links in UI

3. **Add Bot Controls** (start/stop/pause):
   - Currently Config tab is read-only
   - Wire up Flask API bot control endpoints
   - Add buttons to BotStatus component

### **Optional:**

- **Add Historical Charts**: Use account_state history for P&L charts
- **Add Notifications**: Alert on execution errors via email/webhook
- **Multi-Bot Support**: Track multiple bot instances
- **Performance Metrics**: Win rate, Sharpe ratio, max drawdown

---

## Files Changed/Created

### **Python Bot:**
- ✅ `llm-trading-bot/web/database.py` - Added execution tracking columns
- ✅ `llm-trading-bot/run_analysis_bot.py` - Added execution status updates
- ✅ `llm-trading-bot/clear_database.py` - Updated for live/paper modes
- ✅ `llm-trading-bot/scripts/show_errors.py` - Created error viewer
- ✅ `llm-trading-bot/.env` - Added Motherhaven config

### **Next.js Frontend:**
- ✅ `app/llm-bot/types.ts` - Updated BotDecision interface
- ✅ `app/llm-bot/hooks/useBotErrors.ts` - Created error fetching hook
- ✅ `app/llm-bot/hooks/index.ts` - Exported new hooks
- ✅ `app/llm-bot/components/ErrorsTab.tsx` - Created errors display component
- ✅ `app/llm-bot/components/PositionsTable.tsx` - Replaced "Failed" tab with "Errors" tab

### **Main Project:**
- ✅ `.env.local` - Added `LLM_BOT_API_KEY`
- ✅ `MOTHERBOT_INTEGRATION.md` - This file

---

## Summary

The Motherbot integration is now **fully streamlined** and **error-aware**:

✅ Python bot runs anywhere (local, cloud, VPS)
✅ POSTs data to Motherhaven API
✅ Stores in Firebase for real-time display
✅ Tracks execution success/failure
✅ Shows errors in dedicated tab
✅ Local Flask dashboard for debugging
✅ Production Next.js dashboard at `/llm-bot`

**Next**: Rename `app/llm-bot` → `app/motherbot` and test the consolidated interface! 🚀
