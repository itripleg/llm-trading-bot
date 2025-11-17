# Motherhaven Dashboard Integration Guide

This guide explains how to connect your LLM trading bot to the Motherhaven Next.js dashboard for real-time monitoring.

## Overview

The trading bot now supports dual-mode logging:
- **SQLite** (always enabled) - Local database for backup and historical data
- **Motherhaven API** (optional) - Cloud-based dashboard for real-time monitoring

When Motherhaven integration is enabled, the bot automatically POSTs data to your Motherhaven API endpoints while continuing to save locally to SQLite.

## Architecture

```
Trading Bot → TradingLogger → [SQLite Database]
                            → [Motherhaven API] → Firebase → Next.js Dashboard
```

The bot sends the following data:
- **Decisions**: Claude's trade decisions with reasoning
- **Positions**: Position entries and exits with P&L
- **Account State**: Balance, equity, unrealized/realized PnL
- **Bot Status**: Running status and health checks

## Setup Instructions

### Step 1: Configure Motherhaven API

First, ensure your Motherhaven Next.js application is running:

```bash
cd ../motherhaven
npm run dev
```

The dev server should be running at `http://localhost:3000`.

### Step 2: Get API Key

The API key must match between:
1. **Trading bot** `.env` file: `MOTHERHAVEN_API_KEY`
2. **Motherhaven** `.env.local` file: `LLM_BOT_API_KEY`

Find or set the API key in `motherhaven/.env.local`:
```bash
LLM_BOT_API_KEY=your-secret-api-key-12345
```

### Step 3: Configure Trading Bot

Update your trading bot's `.env` file:

```bash
# Motherhaven Dashboard Integration
MOTHERHAVEN_ENABLED=true
MOTHERHAVEN_API_URL=http://localhost:3000
MOTHERHAVEN_API_KEY=your-secret-api-key-12345
MOTHERHAVEN_TIMEOUT=10
```

**Configuration Options:**

- `MOTHERHAVEN_ENABLED`: Set to `true` to enable integration, `false` to disable
- `MOTHERHAVEN_API_URL`: Base URL of your Motherhaven API (use production URL when deployed)
- `MOTHERHAVEN_API_KEY`: Secret API key for authentication (must match Motherhaven's `LLM_BOT_API_KEY`)
- `MOTHERHAVEN_TIMEOUT`: Request timeout in seconds (default: 10)

### Step 4: Test the Integration

Run the integration test script:

```bash
python test_motherhaven_integration.py
```

This will:
1. Verify your configuration
2. Test direct API calls to Motherhaven
3. Test the TradingLogger integration
4. Send sample data to verify connectivity

Expected output:
```
✓ Configuration Check: PASSED
✓ Direct MotherhavenLogger: PASSED
✓ TradingLogger Integration: PASSED

Total: 3 passed, 0 failed, 0 skipped
```

### Step 5: Verify Dashboard

Open the Motherhaven dashboard:
```
http://localhost:3000/llm-bot
```

You should see test data from the integration test:
- Bot status showing "running"
- Recent decisions
- Account state with test balance
- Test positions

### Step 6: Start Trading Bot

Start the bot normally:

```bash
# Paper trading mode
python run_analysis_bot.py

# Or use the orchestrator
python start_bot.py
```

The bot will now automatically send all data to both SQLite and Motherhaven!

## How It Works

### Automatic Dual Logging

The `TradingLogger` class automatically handles dual logging:

```python
from trading.logger import TradingLogger

logger = TradingLogger()

# This logs to BOTH SQLite and Motherhaven (if enabled)
logger.log_decision(decision, raw_response)
logger.log_account_state(balance=1000, equity=1050, ...)
logger.log_position_entry(...)
logger.log_position_exit(...)
logger.log_bot_status('running', 'Trading cycle completed')
```

**No code changes needed** in your existing bot scripts! The integration happens transparently.

### Error Handling

If Motherhaven API is unavailable:
- The bot continues running normally
- Data is still saved to SQLite
- Warnings are logged but the bot doesn't crash
- The bot will retry on the next cycle

Example log output:
```
[Motherhaven] Integration enabled - posting to http://localhost:3000
[Motherhaven] Successfully posted to /api/llm-bot/ingest/decision
[WARNING] [Motherhaven] Failed to log position: Connection refused
```

## API Endpoints

The bot POSTs to these Motherhaven endpoints:

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `POST /api/llm-bot/ingest/decision` | Claude trade decisions | Every trading cycle (~3 min) |
| `POST /api/llm-bot/ingest/account` | Account balance & PnL | Every trading cycle |
| `POST /api/llm-bot/ingest/position` | Position entries/exits | When trades execute |
| `POST /api/llm-bot/ingest/status` | Bot health status | Every trading cycle |

All requests include:
- `Content-Type: application/json` header
- `x-api-key: {your-api-key}` header for authentication

## Deployment Considerations

### Local Development
- Use `http://localhost:3000` as the API URL
- Both bot and Motherhaven run on the same machine

### Production Deployment
- Deploy Motherhaven to Vercel/Netlify/etc.
- Update `MOTHERHAVEN_API_URL` to your production URL (e.g., `https://your-app.vercel.app`)
- Keep the bot running on your local machine or VPS
- Ensure the bot can reach your production URL (check firewall/network)

### Multiple Bot Instances
- Each bot instance can log to the same Motherhaven dashboard
- Use the same `MOTHERHAVEN_API_KEY` for all instances
- Data is aggregated in Firebase and displayed together
- Great for testing multiple strategies or LLMs simultaneously

### Security
- **API Key**: Keep your `MOTHERHAVEN_API_KEY` secret
- Don't commit it to Git (use `.env` files, which are gitignored)
- Use different API keys for production vs development
- Consider using environment-specific keys if running multiple dashboards

## Troubleshooting

### "Configuration issues found"
**Problem**: Missing or invalid Motherhaven configuration

**Solution**: Verify `.env` file has all required fields:
```bash
MOTHERHAVEN_ENABLED=true
MOTHERHAVEN_API_URL=http://localhost:3000
MOTHERHAVEN_API_KEY=your-key-here
```

### "Connection refused" or "Timeout"
**Problem**: Cannot reach Motherhaven API

**Solutions**:
1. Check Motherhaven dev server is running: `cd ../motherhaven && npm run dev`
2. Verify the API URL is correct (should be `http://localhost:3000` for local)
3. Check firewall isn't blocking the connection
4. Try accessing the URL in a browser: `http://localhost:3000/llm-bot`

### "401 Unauthorized" or "403 Forbidden"
**Problem**: API key mismatch

**Solutions**:
1. Check `MOTHERHAVEN_API_KEY` in bot `.env` matches `LLM_BOT_API_KEY` in Motherhaven `.env.local`
2. Restart the Motherhaven dev server after changing the API key
3. Restart the trading bot after changing the API key

### Data not appearing in dashboard
**Problem**: Bot is running but dashboard shows no data

**Solutions**:
1. Check bot logs for Motherhaven-related errors
2. Verify `MOTHERHAVEN_ENABLED=true` in bot `.env`
3. Check browser console for frontend errors
4. Verify Firebase is configured correctly in Motherhaven
5. Run the integration test: `python test_motherhaven_integration.py`

### "Failed to log" warnings in bot logs
**Problem**: Motherhaven API calls failing

**Solutions**:
1. Check Motherhaven server logs for errors
2. Verify API endpoints are implemented correctly
3. Check Firebase credentials in Motherhaven `.env.local`
4. These warnings won't stop the bot - data is still saved to SQLite

## Disabling Motherhaven

To disable the integration and only use SQLite:

```bash
# In .env
MOTHERHAVEN_ENABLED=false
```

Or simply comment out the line:
```bash
# MOTHERHAVEN_ENABLED=true
```

The bot will log: `[Motherhaven] Integration disabled - only logging to SQLite`

## File Reference

**New Files:**
- `web/motherhaven_logger.py` - Motherhaven API client
- `test_motherhaven_integration.py` - Integration test suite
- `MOTHERHAVEN_INTEGRATION.md` - This guide

**Modified Files:**
- `config/settings.py` - Added Motherhaven configuration fields
- `trading/logger.py` - Integrated Motherhaven logging into TradingLogger
- `.env.example` - Added Motherhaven configuration template

**No Changes Required:**
- `run_analysis_bot.py` - Works automatically with new logger
- `start_bot.py` - No changes needed
- `trading/account.py` - No changes needed
- `trading/executor.py` - No changes needed

## Benefits

### Why Use Motherhaven?

**vs. Local Flask Dashboard:**
- ✅ Modern, responsive UI built with Next.js and React
- ✅ Cloud-accessible (can monitor from anywhere)
- ✅ Real-time updates with efficient polling
- ✅ Better performance and scalability
- ✅ Firebase-backed (automatic backups, no local DB management)
- ✅ Easy to deploy to production
- ✅ Supports multiple bot instances naturally

**Dual Logging Advantages:**
- ✅ SQLite provides local backup if API is down
- ✅ Motherhaven provides beautiful real-time dashboard
- ✅ Both systems work independently
- ✅ Can switch between them without losing data
- ✅ SQLite useful for debugging and analysis
- ✅ Motherhaven useful for live monitoring

## Next Steps

1. ✅ Complete the setup above
2. ✅ Run the integration test
3. ✅ Verify data appears in dashboard
4. ✅ Start the trading bot in paper mode
5. Monitor the dashboard at `http://localhost:3000/llm-bot`
6. Review Claude's decisions and bot performance
7. When ready, switch to live trading (carefully!)

## Support

- **Bot Issues**: Check `logs/` directory for detailed logs
- **Dashboard Issues**: Check Motherhaven repository
- **Integration Issues**: Run `python test_motherhaven_integration.py` for diagnostics

---

**Last Updated**: 2025-01-17
