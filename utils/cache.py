"""
Simple Redis cache for motherbot.
Caches market prices and account state to reduce API calls.
"""

import redis
import json
from typing import Optional, Any
from datetime import datetime


class SimpleCache:
    """Dead simple Redis cache - just makes the bot faster."""

    def __init__(self, host='localhost', port=6379):
        self.redis = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=2
        )

        # Test connection
        try:
            self.redis.ping()
            print(f"[Cache] Connected to Redis at {host}:{port}")
        except Exception as e:
            print(f"[Cache] WARNING: Redis not available: {e}")
            print(f"[Cache] Bot will work but slower (no caching)")
            self.redis = None

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None

        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"[Cache] Error getting {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 60):
        """
        Set value in cache with TTL (time to live in seconds).

        Args:
            key: Cache key
            value: Any JSON-serializable value
            ttl: Seconds until expiration (default: 60s)
        """
        if not self.redis:
            return False

        try:
            self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            print(f"[Cache] Error setting {key}: {e}")
            return False

    def delete(self, key: str):
        """Delete a key from cache."""
        if not self.redis:
            return False

        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"[Cache] Error deleting {key}: {e}")
            return False

    def clear_pattern(self, pattern: str):
        """Clear all keys matching a pattern (e.g., 'price:*')."""
        if not self.redis:
            return 0

        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            print(f"[Cache] Error clearing {pattern}: {e}")
            return 0


# Singleton instance
_cache = None

def get_cache() -> SimpleCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = SimpleCache()
    return _cache


# Convenience functions for common caching patterns

def cache_price(coin: str, price: float, ttl: int = 30):
    """Cache a coin price for 30 seconds (avoid hammering Hyperliquid)."""
    cache = get_cache()
    data = {
        'price': price,
        'timestamp': datetime.now().isoformat()
    }
    cache.set(f'price:{coin}', data, ttl=ttl)


def get_cached_price(coin: str) -> Optional[float]:
    """Get cached price if available."""
    cache = get_cache()
    data = cache.get(f'price:{coin}')
    if data:
        return data.get('price')
    return None


def cache_account_state(balance: float, equity: float, positions: list, ttl: int = 60):
    """Cache account state to avoid constant queries."""
    cache = get_cache()
    data = {
        'balance': balance,
        'equity': equity,
        'positions': positions,
        'timestamp': datetime.now().isoformat()
    }
    cache.set('account:state', data, ttl=ttl)


def get_cached_account_state() -> Optional[dict]:
    """Get cached account state if available."""
    cache = get_cache()
    return cache.get('account:state')


if __name__ == '__main__':
    # Test the cache
    print("Testing SimpleCache...")

    cache = get_cache()

    # Test price caching
    print("\n[1] Testing price cache...")
    cache_price('BTC/USDC:USDC', 95000.50)
    cached = get_cached_price('BTC/USDC:USDC')
    print(f"Cached price: ${cached:,.2f}")

    # Test account state caching
    print("\n[2] Testing account state cache...")
    cache_account_state(
        balance=1000.0,
        equity=950.0,
        positions=[{'coin': 'BTC', 'pnl': -50.0}]
    )
    state = get_cached_account_state()
    print(f"Cached state: {state}")

    # Test TTL
    print("\n[3] Testing TTL...")
    cache.set('test:ttl', {'test': 'data'}, ttl=5)
    import time
    print("Waiting 6 seconds...")
    time.sleep(6)
    expired = cache.get('test:ttl')
    print(f"After TTL expired: {expired}")

    print("\n[OK] Cache is working!")
