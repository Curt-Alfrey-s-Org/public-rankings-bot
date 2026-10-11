"""
In-Memory Caching for Rankings API

Provides high-performance read caching for ranking queries.
Automatically invalidates when data is refreshed.

Pattern:
1. On startup: Load all rankings into memory cache
2. On reads: Serve from memory cache (fast)
3. On refresh/write: Invalidate specific cache sections + write cache version file
4. Cache miss: Query database directly
"""

import threading
import logging
import json
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class RankingsCache:
    """
    Thread-safe in-memory cache for rankings data.
    Maintains separate caches per ranking type and manages invalidation.
    """
    
    def __init__(self, cache_version_file: Optional[Path] = None):
        """
        Initialize rankings cache.
        
        Args:
            cache_version_file: Path to cache version tracking file
        """
        self._lock = threading.RLock()
        self._cache: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict] = {}
        self.cache_version_file = cache_version_file
        self._version = 0
        self._last_updated = None
        
        logger.info(f"RankingsCache initialized (version file: {cache_version_file})")
    
    def load_version(self) -> int:
        """Load cache version from file."""
        if self.cache_version_file and self.cache_version_file.exists():
            try:
                with open(self.cache_version_file, 'r') as f:
                    data = json.load(f)
                    self._version = data.get('version', 0)
                    logger.info(f"Cache version loaded: {self._version}")
                    return self._version
            except Exception as e:
                logger.warning(f"Failed to load cache version: {e}")
        return 0
    
    def save_version(self):
        """Save cache version to file."""
        if self.cache_version_file:
            try:
                self.cache_version_file.parent.mkdir(exist_ok=True, parents=True)
                with open(self.cache_version_file, 'w') as f:
                    json.dump({
                        'version': self._version,
                        'updated_at': datetime.now().isoformat(),
                        'cached_types': list(self._cache.keys())
                    }, f, indent=2)
                logger.debug(f"Cache version saved: {self._version}")
            except Exception as e:
                logger.warning(f"Failed to save cache version: {e}")
    
    def set(self, key: str, value: Any, metadata: Optional[Dict] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key (e.g., 'wpba-women', 'wpa-men')
            value: Data to cache
            metadata: Optional metadata about the cache entry
        """
        with self._lock:
            self._cache[key] = value
            if metadata:
                self._metadata[key] = metadata
            self._last_updated = datetime.now()
            logger.debug(f"Cache set: {key} ({len(str(value))} bytes)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        with self._lock:
            if key in self._cache:
                logger.debug(f"Cache hit: {key}")
                return self._cache[key]
            else:
                logger.debug(f"Cache miss: {key}")
                return None
    
    def get_metadata(self, key: str) -> Optional[Dict]:
        """Get metadata for cached entry."""
        with self._lock:
            return self._metadata.get(key)
    
    def invalidate(self, key: Optional[str] = None):
        """
        Invalidate cache entry or entire cache.
        
        Args:
            key: Specific key to invalidate. If None, invalidates all.
        """
        with self._lock:
            if key is None:
                # Clear entire cache
                self._cache.clear()
                self._metadata.clear()
                logger.info("Cache fully invalidated (all entries cleared)")
            else:
                # Clear specific entry
                if key in self._cache:
                    del self._cache[key]
                if key in self._metadata:
                    del self._metadata[key]
                logger.info(f"Cache invalidated: {key}")
            
            self._version += 1
            self.save_version()
    
    def clear(self):
        """Clear all cache entries."""
        self.invalidate()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total_size = sum(len(str(v)) for v in self._cache.values())
            return {
                'entries': len(self._cache),
                'size_bytes': total_size,
                'version': self._version,
                'last_updated': self._last_updated.isoformat() if self._last_updated else None,
                'cached_keys': list(self._cache.keys())
            }


# Global cache instance
_global_cache = None


def get_global_cache(cache_version_file: Optional[Path] = None) -> RankingsCache:
    """
    Get or create global cache instance (singleton).
    
    Args:
        cache_version_file: Path to cache version file
        
    Returns:
        Global RankingsCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = RankingsCache(cache_version_file)
    return _global_cache


# Cache invalidation patterns for different operations

def cache_rankings_set(ranking_type: str, rankings_data: List[Dict]):
    """
    Cache rankings data for a ranking type.
    
    Args:
        ranking_type: Ranking type key (e.g., 'wpba-women')
        rankings_data: Ranking records to cache
    """
    cache = get_global_cache()
    cache.set(
        ranking_type,
        rankings_data,
        metadata={
            'timestamp': datetime.now().isoformat(),
            'count': len(rankings_data)
        }
    )
    logger.info(f"Cached {len(rankings_data)} rankings for {ranking_type}")


def cache_rankings_get(ranking_type: str) -> Optional[List[Dict]]:
    """
    Get cached rankings for a ranking type.
    
    Args:
        ranking_type: Ranking type key
        
    Returns:
        Cached records or None if not in cache
    """
    cache = get_global_cache()
    return cache.get(ranking_type)


def cache_invalidate_rankings(ranking_type: Optional[str] = None):
    """
    Invalidate rankings cache.
    Typically called after a refresh operation.
    
    Args:
        ranking_type: Specific ranking type to invalidate.
                     If None, invalidates all ranking caches.
    """
    cache = get_global_cache()
    
    if ranking_type is None:
        # Invalidate all rankings
        cache.clear()
        logger.info("All rankings cache invalidated")
    else:
        # Invalidate specific ranking type
        cache.invalidate(ranking_type)
        logger.info(f"Rankings cache invalidated for {ranking_type}")


def get_cache_stats() -> Dict:
    """Get current cache statistics."""
    cache = get_global_cache()
    return cache.get_stats()
