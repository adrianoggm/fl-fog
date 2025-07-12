"""
Model Cache for Fog Computing Layer.

Provides intelligent caching of ML models and training updates
to reduce communication overhead and improve response times.
"""

import asyncio
import time
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached model or data entry."""
    key: str
    data: Any
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl: Optional[timedelta] = None
    metadata: Dict[str, Any] = None


class ModelCache:
    """
    Intelligent model cache for fog computing layer.
    
    Features:
    - LRU eviction policy
    - TTL-based expiration
    - Size-based limits
    - Access pattern tracking
    - Persistence to disk
    """
    
    def __init__(
        self,
        cache_size: float = 10.0,  # GB
        ttl_hours: float = 24.0,
        persistence_path: Optional[str] = None
    ):
        self.max_size_bytes = int(cache_size * 1024 * 1024 * 1024)  # Convert GB to bytes
        self.default_ttl = timedelta(hours=ttl_hours)
        self.persistence_path = Path(persistence_path) if persistence_path else None
        
        # Cache storage
        self.cache: Dict[str, CacheEntry] = {}
        self.current_size = 0
        
        # Access tracking
        self.access_order: List[str] = []  # For LRU
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_requests": 0
        }
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"Model cache initialized with {cache_size}GB capacity")
    
    async def start(self) -> None:
        """Start the cache service."""
        if self._running:
            return
        
        self._running = True
        
        # Load persisted cache if available
        if self.persistence_path and self.persistence_path.exists():
            await self._load_from_disk()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Model cache started")
    
    async def stop(self) -> None:
        """Stop the cache service."""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Persist cache to disk
        if self.persistence_path:
            await self._save_to_disk()
        
        logger.info("Model cache stopped")
    
    async def put(
        self,
        key: str,
        data: Any,
        ttl: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store data in cache."""
        try:
            # Serialize data to calculate size
            serialized_data = pickle.dumps(data)
            size_bytes = len(serialized_data)
            
            # Check if data fits in cache
            if size_bytes > self.max_size_bytes:
                logger.warning(f"Data too large for cache: {size_bytes} bytes")
                return False
            
            # Make space if needed
            await self._make_space(size_bytes)
            
            # Create cache entry
            now = datetime.now()
            entry = CacheEntry(
                key=key,
                data=data,
                size_bytes=size_bytes,
                created_at=now,
                last_accessed=now,
                access_count=0,
                ttl=ttl or self.default_ttl,
                metadata=metadata or {}
            )
            
            # Remove existing entry if present
            if key in self.cache:
                await self._remove_entry(key)
            
            # Add new entry
            self.cache[key] = entry
            self.current_size += size_bytes
            self.access_order.append(key)
            
            logger.debug(f"Cached {key} ({size_bytes} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve data from cache."""
        self.stats["total_requests"] += 1
        
        if key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        entry = self.cache[key]
        
        # Check TTL
        if entry.ttl and datetime.now() - entry.created_at > entry.ttl:
            await self._remove_entry(key)
            self.stats["misses"] += 1
            return None
        
        # Update access info
        entry.last_accessed = datetime.now()
        entry.access_count += 1
        
        # Move to end of access order (most recently used)
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        self.stats["hits"] += 1
        logger.debug(f"Cache hit for {key}")
        
        return entry.data
    
    async def contains(self, key: str) -> bool:
        """Check if key exists in cache."""
        if key not in self.cache:
            return False
        
        entry = self.cache[key]
        
        # Check TTL
        if entry.ttl and datetime.now() - entry.created_at > entry.ttl:
            await self._remove_entry(key)
            return False
        
        return True
    
    async def remove(self, key: str) -> bool:
        """Remove entry from cache."""
        return await self._remove_entry(key)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.access_order.clear()
        self.current_size = 0
        logger.info("Cache cleared")
    
    async def _remove_entry(self, key: str) -> bool:
        """Remove a specific cache entry."""
        if key not in self.cache:
            return False
        
        entry = self.cache[key]
        self.current_size -= entry.size_bytes
        del self.cache[key]
        
        if key in self.access_order:
            self.access_order.remove(key)
        
        logger.debug(f"Removed {key} from cache")
        return True
    
    async def _make_space(self, required_bytes: int) -> None:
        """Make space in cache using LRU eviction."""
        while self.current_size + required_bytes > self.max_size_bytes and self.access_order:
            # Remove least recently used entry
            lru_key = self.access_order[0]
            await self._remove_entry(lru_key)
            self.stats["evictions"] += 1
            logger.debug(f"Evicted {lru_key} to make space")
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries from cache."""
        expired_keys = []
        now = datetime.now()
        
        for key, entry in self.cache.items():
            if entry.ttl and now - entry.created_at > entry.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            await self._remove_entry(key)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired entries")
        
        return len(expired_keys)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                await self.cleanup_expired()
                await asyncio.sleep(300)  # Cleanup every 5 minutes
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["total_requests"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            "entries": len(self.cache),
            "size_bytes": self.current_size,
            "size_mb": round(self.current_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2),
            "utilization": self.current_size / self.max_size_bytes,
            "hit_rate": round(hit_rate, 3),
            "stats": self.stats.copy()
        }
    
    async def _save_to_disk(self) -> None:
        """Persist cache to disk."""
        if not self.persistence_path:
            return
        
        try:
            cache_data = {
                "cache": self.cache,
                "access_order": self.access_order,
                "current_size": self.current_size,
                "stats": self.stats
            }
            
            with open(self.persistence_path, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"Cache persisted to {self.persistence_path}")
            
        except Exception as e:
            logger.error(f"Failed to persist cache: {e}")
    
    async def _load_from_disk(self) -> None:
        """Load cache from disk."""
        try:
            with open(self.persistence_path, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.cache = cache_data.get("cache", {})
            self.access_order = cache_data.get("access_order", [])
            self.current_size = cache_data.get("current_size", 0)
            self.stats = cache_data.get("stats", self.stats)
            
            # Validate loaded data
            await self._validate_loaded_cache()
            
            logger.info(f"Cache loaded from {self.persistence_path}")
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            # Reset cache on load failure
            await self.clear()
    
    async def _validate_loaded_cache(self) -> None:
        """Validate and cleanup loaded cache data."""
        invalid_keys = []
        
        for key, entry in self.cache.items():
            # Check TTL
            if entry.ttl and datetime.now() - entry.created_at > entry.ttl:
                invalid_keys.append(key)
                continue
            
            # Validate entry structure
            if not hasattr(entry, 'data') or not hasattr(entry, 'size_bytes'):
                invalid_keys.append(key)
        
        # Remove invalid entries
        for key in invalid_keys:
            await self._remove_entry(key)
        
        if invalid_keys:
            logger.info(f"Removed {len(invalid_keys)} invalid entries during validation")
    
    # Model-specific methods
    
    async def cache_model(
        self,
        model_id: str,
        model_weights: Dict[str, Any],
        version: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Cache a model with version info."""
        cache_key = f"model:{model_id}:{version}"
        model_metadata = {
            "model_id": model_id,
            "version": version,
            "type": "model_weights",
            **(metadata or {})
        }
        
        return await self.put(cache_key, model_weights, metadata=model_metadata)
    
    async def get_model(self, model_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Get a specific model version."""
        cache_key = f"model:{model_id}:{version}"
        return await self.get(cache_key)
    
    async def get_latest_model(self, model_id: str = "global") -> Optional[Dict[str, Any]]:
        """Get the latest cached model."""
        # Find the latest version
        latest_version = None
        latest_timestamp = None
        
        for key, entry in self.cache.items():
            if key.startswith(f"model:{model_id}:") and entry.metadata:
                if entry.metadata.get("type") == "model_weights":
                    if latest_timestamp is None or entry.created_at > latest_timestamp:
                        latest_timestamp = entry.created_at
                        latest_version = entry.metadata.get("version")
        
        if latest_version:
            return await self.get_model(model_id, latest_version)
        
        return None
    
    async def cache_aggregation_result(
        self,
        round_id: str,
        aggregated_weights: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Cache aggregation result."""
        cache_key = f"aggregation:{round_id}"
        agg_metadata = {
            "round_id": round_id,
            "type": "aggregation_result",
            **(metadata or {})
        }
        
        return await self.put(cache_key, aggregated_weights, metadata=agg_metadata)
