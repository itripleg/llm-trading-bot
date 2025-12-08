# Redis Cache Setup (Quick & Simple)

## What This Does

Speeds up your bot by caching:
- Market prices (30 seconds)
- Account state (60 seconds)

**Result:** Faster bot, fewer API calls, save money.

---

## Setup

### 1. Redis is already running! ✅
You have Redis on `localhost:6379`

### 2. Install Python library
```bash
cd motherbot
pip install redis
```

### 3. Use it in your code

```python
from utils.cache import cache_price, get_cached_price

# Before fetching price, check cache
cached = get_cached_price('BTC/USDC:USDC')
if cached:
    print(f"Using cached price: ${cached:,.2f}")
else:
    # Fetch from API
    price = fetch_from_hyperliquid('BTC/USDC:USDC')
    cache_price('BTC/USDC:USDC', price, ttl=30)  # Cache for 30s
```

---

## Example: Cache in Data Fetcher

```python
# In data/fetcher.py
from utils.cache import cache_price, get_cached_price

def fetch_ticker(self, symbol):
    # Check cache first
    cached = get_cached_price(symbol)
    if cached:
        return {'last': cached}

    # Not cached - fetch from API
    ticker = self.exchange.fetch_ticker(symbol)
    price = ticker['last']

    # Cache for 30 seconds
    cache_price(symbol, price, ttl=30)

    return ticker
```

---

## Example: Cache Account State

```python
# In trading/account.py or run_analysis_bot.py
from utils.cache import cache_account_state, get_cached_account_state

# Check cache first
cached = get_cached_account_state()
if cached:
    print(f"Using cached account state")
    return cached

# Fetch from Hyperliquid
state = executor.get_account_state()
cache_account_state(
    balance=state['balance'],
    equity=state['equity'],
    positions=state['positions'],
    ttl=60  # Cache for 1 minute
)
```

---

## Benefits

**Before:**
- Every cycle fetches fresh data from APIs
- Slow (wait for API responses)
- Hits API rate limits faster

**After:**
- Cache hit = instant response (< 1ms)
- Faster bot cycles
- Fewer API calls = save money
- Still updates every 30-60 seconds (fresh enough)

---

## Cache Keys

The cache uses these keys:
```
price:BTC/USDC:USDC      (30s TTL)
price:ETH/USDC:USDC      (30s TTL)
account:state            (60s TTL)
```

---

## Monitor Cache

```python
from utils.cache import get_cache

cache = get_cache()

# Check if key exists
price = cache.get('price:BTC/USDC:USDC')
print(price)

# Clear cache for a coin
cache.delete('price:BTC/USDC:USDC')

# Clear all prices
cache.clear_pattern('price:*')
```

---

## That's It!

Redis is running, cache is ready. Use it wherever you're hitting APIs repeatedly.

**Keep it simple, make money faster.** 💰
