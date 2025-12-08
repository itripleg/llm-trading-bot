# Running Multiple Bot Instances

This guide explains how to run multiple bot instances, each focused on different coins.

## Configuration Options

### Option 1: Single Bot Analyzing Multiple Coins (Default)

By default, if you don't set `ACTIVE_TRADING_ASSETS`, the bot will analyze **ALL** coins listed in `TRADING_ASSETS`.

**.env example:**
```bash
TRADING_ASSETS=BTC/USDC:USDC,ETH/USDC:USDC,SOL/USDC:USDC,ADA/USDC:USDC
# Leave ACTIVE_TRADING_ASSETS empty to analyze all 4 coins each cycle
```

The bot will fetch market data and make decisions for BTC, ETH, SOL, and ADA every cycle.

### Option 2: Single Bot Focused on Specific Coins

Set `ACTIVE_TRADING_ASSETS` to only analyze specific coins each cycle.

**.env example:**
```bash
TRADING_ASSETS=BTC/USDC:USDC,ETH/USDC:USDC,SOL/USDC:USDC,ADA/USDC:USDC
ACTIVE_TRADING_ASSETS=BTC/USDC:USDC,ETH/USDC:USDC
```

The bot will only analyze BTC and ETH, but can still trade the other coins if needed.

### Option 3: Multiple Bot Instances with Different Focuses

Run separate bot instances using different environment variable configurations.

## Running Multiple Instances

### Method 1: Different .env Files

Create separate environment files for each bot:

**Bot 1 - .env.btc:**
```bash
TRADING_ASSETS=BTC/USDC:USDC
ACTIVE_TRADING_ASSETS=BTC/USDC:USDC
TRADING_MODE=live
MAX_POSITION_SIZE_USD=50
# ... other settings
```

**Bot 2 - .env.eth:**
```bash
TRADING_ASSETS=ETH/USDC:USDC
ACTIVE_TRADING_ASSETS=ETH/USDC:USDC
TRADING_MODE=live
MAX_POSITION_SIZE_USD=30
# ... other settings
```

Run each bot with its own .env file:
```bash
# Terminal 1 - BTC Bot
uv run --env-file .env.btc python run_analysis_bot.py start

# Terminal 2 - ETH Bot
uv run --env-file .env.eth python run_analysis_bot.py start
```

### Method 2: Override with Environment Variables

Run bots with inline environment variable overrides:

```bash
# Terminal 1 - BTC Bot
ACTIVE_TRADING_ASSETS="BTC/USDC:USDC" MAX_POSITION_SIZE_USD=50 uv run python run_analysis_bot.py start

# Terminal 2 - ETH Bot
ACTIVE_TRADING_ASSETS="ETH/USDC:USDC" MAX_POSITION_SIZE_USD=30 uv run python run_analysis_bot.py start

# Terminal 3 - Multi-coin Bot
ACTIVE_TRADING_ASSETS="SOL/USDC:USDC,ADA/USDC:USDC" MAX_POSITION_SIZE_USD=20 uv run python run_analysis_bot.py start
```

### Method 3: Separate Bot Directories

For complete isolation, duplicate the bot directory:

```bash
cd /path/to/motherhaven/motherbot
cp -r . ../motherbot-btc
cp -r . ../motherbot-eth

# Edit .env in each directory
cd ../motherbot-btc
# Edit .env to focus on BTC
uv run python run_analysis_bot.py start

cd ../motherbot-eth
# Edit .env to focus on ETH
uv run python run_analysis_bot.py start
```

## Important Considerations

### Database Separation

Each bot instance writes to its own database:
- **Live mode:** `data/trading_bot_live.db`
- **Paper mode:** `data/trading_bot_paper.db`

⚠️ **Warning:** Multiple bots using the same database in live mode can cause conflicts!

**Solution:** Use separate directories (Method 3) or modify the database path in each instance.

### Wallet Management

If running multiple live trading bots:
- All bots share the same Hyperliquid wallet (from `HYPERLIQUID_WALLET_PRIVATE_KEY`)
- Make sure total position sizes across all bots don't exceed your risk tolerance
- Monitor total account exposure across all bot instances

### Resource Usage

Each bot instance:
- Uses Claude API tokens (monitor your Anthropic usage)
- Makes Hyperliquid API calls (watch rate limits)
- Runs every 2.5 minutes (150 seconds)

Consider staggering bot start times to avoid simultaneous API calls.

## Example Multi-Bot Setup

**Scenario:** Run 3 bots focused on different coin categories

**Bot 1 - Major Coins (.env.major):**
```bash
ACTIVE_TRADING_ASSETS=BTC/USDC:USDC,ETH/USDC:USDC
MAX_POSITION_SIZE_USD=50
MAX_LEVERAGE=10
```

**Bot 2 - Layer 1s (.env.l1):**
```bash
ACTIVE_TRADING_ASSETS=SOL/USDC:USDC,ADA/USDC:USDC
MAX_POSITION_SIZE_USD=30
MAX_LEVERAGE=15
```

**Bot 3 - High Risk (.env.alts):**
```bash
ACTIVE_TRADING_ASSETS=DOGE/USDC:USDC,AVAX/USDC:USDC
MAX_POSITION_SIZE_USD=20
MAX_LEVERAGE=20
```

Start all three:
```bash
uv run --env-file .env.major python run_analysis_bot.py start &
sleep 50  # Stagger starts
uv run --env-file .env.l1 python run_analysis_bot.py start &
sleep 50
uv run --env-file .env.alts python run_analysis_bot.py start &
```

## Monitoring Multiple Bots

Use the web dashboard to monitor all bots:
```bash
uv run python web/app.py
```

Visit http://localhost:5000 to see combined activity across all bot instances (if they share the same database).

## Best Practices

1. **Start with one bot** to validate your strategy
2. **Use paper trading mode** when testing multiple bot configurations
3. **Monitor total exposure** across all live bot instances
4. **Set conservative position sizes** per bot to avoid over-leverage
5. **Use ACTIVE_TRADING_ASSETS** to prevent redundant analysis of the same coins
6. **Stagger execution times** to spread out API calls
7. **Monitor Claude API usage** - multiple bots = more token consumption

## Troubleshooting

### Bots analyzing the same coin multiple times

**Problem:** You see "Analyzing assets: BTC/USDC:USDC, BTC/USDC:USDC, BTC/USDC:USDC"

**Solution:** Check that `ACTIVE_TRADING_ASSETS` is set correctly and doesn't have duplicates

### Database conflicts

**Problem:** Multiple bots writing to the same database causing position tracking issues

**Solution:** Use separate bot directories or modify database paths in settings

### API rate limits

**Problem:** Too many API calls when running multiple bots

**Solution:**
- Increase `EXECUTION_INTERVAL_SECONDS`
- Stagger bot start times
- Reduce number of simultaneous bots

## Summary

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| Single bot, all coins | Simple, one process | Less flexibility | Small portfolios |
| Single bot, subset | Easy config | Still limited | Testing specific strategies |
| Multiple .env files | Good separation | More complex setup | Different risk profiles |
| Separate directories | Complete isolation | More disk space | Production multi-strategy |

Choose the method that fits your trading strategy and risk management needs!
