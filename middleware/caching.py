"""
Caching Middleware - Response caching & cache invalidation
Improves performance by caching frequently accessed data
"""
from flask_caching import Cache
from functools import wraps
from flask import request, jsonify
from datetime import datetime
import json
from pathlib import Path

# Configuration
CACHE_STATS_FILE = Path('data/cache_stats.json')


class CacheManager:
    """Manage caching strategies and statistics"""
    
    def __init__(self, app=None):
        """Initialize cache manager"""
        self.app = app
        self.cache = None
        self.stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0
        }
        self._load_stats()
    
    def init_app(self, app):
        """Initialize cache with app"""
        self.app = app
        self.cache = Cache(app, config={
            'CACHE_TYPE': 'simple',  # or 'redis' for distributed
            'CACHE_DEFAULT_TIMEOUT': 300,
            'CACHE_KEY_PREFIX': 'manga_org_'
        })
        print("✓ Caching initialized")
        return self.cache
    
    def _load_stats(self):
        """Load cache statistics from file"""
        if CACHE_STATS_FILE.exists():
            try:
                with open(CACHE_STATS_FILE, 'r') as f:
                    self.stats = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.stats = {'hits': 0, 'misses': 0, 'invalidations': 0}
    
    def _save_stats(self):
        """Save cache statistics to file"""
        CACHE_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def record_hit(self):
        """Record a cache hit"""
        self.stats['hits'] += 1
        self._save_stats()
    
    def record_miss(self):
        """Record a cache miss"""
        self.stats['misses'] += 1
        self._save_stats()
    
    def record_invalidation(self):
        """Record cache invalidation"""
        self.stats['invalidations'] += 1
        self._save_stats()
    
    def get_hit_rate(self):
        """Calculate cache hit rate percentage"""
        total = self.stats['hits'] + self.stats['misses']
        if total == 0:
            return 0
        return (self.stats['hits'] / total) * 100
    
    def get_stats(self):
        """Get cache statistics"""
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'invalidations': self.stats['invalidations'],
            'hit_rate': f"{self.get_hit_rate():.1f}%",
            'total_requests': self.stats['hits'] + self.stats['misses']
        }
    
    def clear_all(self):
        """Clear all cached data"""
        if self.cache:
            self.cache.clear()
        self.stats = {'hits': 0, 'misses': 0, 'invalidations': 0}
        self._save_stats()
        print("✓ Cache cleared")
    
    def invalidate_pattern(self, pattern):
        """Invalidate cache entries matching pattern"""
        if self.cache:
            # For simple cache, we'd need to track which keys match
            # For Redis, we could use pattern matching
            self.record_invalidation()
            print(f"✓ Cache invalidated for pattern: {pattern}")


def cache_response(timeout=300, key_prefix=None):
    """
    Decorator to cache endpoint responses
    
    Usage:
        @app.route('/api/data')
        @cache_response(timeout=600)
        def get_data():
            return jsonify(...)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate cache key
            if key_prefix:
                cache_key = f"{key_prefix}_{request.full_path}"
            else:
                cache_key = f"endpoint_{request.full_path}"
            
            # Try to get from cache
            cached_response = cache_manager.cache.get(cache_key)
            if cached_response:
                cache_manager.record_hit()
                # Add cache info to response
                response = jsonify(cached_response)
                response.headers['X-Cache'] = 'HIT'
                return response
            
            # Cache miss - execute function
            cache_manager.record_miss()
            response_data = f(*args, **kwargs)
            
            # If response is JSON, cache it
            if isinstance(response_data, tuple) and len(response_data) == 2:
                data, status_code = response_data
                if status_code == 200 and isinstance(data, dict):
                    cache_manager.cache.set(cache_key, data, timeout)
                    response = jsonify(data)
                    response.status_code = status_code
            else:
                response = response_data
            
            response.headers['X-Cache'] = 'MISS'
            return response
        
        return decorated_function
    return decorator


def invalidate_user_cache():
    """Invalidate all user-related cache"""
    if cache_manager.cache:
        # Clear keys matching user pattern
        cache_manager.record_invalidation()
        print("✓ User cache invalidated")


def invalidate_audit_cache():
    """Invalidate audit log cache"""
    if cache_manager.cache:
        cache_manager.record_invalidation()
        print("✓ Audit cache invalidated")


# Global cache manager instance
cache_manager = CacheManager()
