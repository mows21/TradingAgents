"""
Cache Management Module for TradingAgents

This module provides comprehensive cache management functionality including:
- Cache cleanup and retention policies
- Cache statistics tracking (hit/miss rates, API usage)
- Cache versioning for schema invalidation
- Automatic cache maintenance

Usage:
    from tradingagents.dataflows.cache_manager import CacheManager

    cache_mgr = CacheManager()
    cache_mgr.cleanup_old_cache()
    stats = cache_mgr.get_statistics()
"""

import os
import time
import json
import hashlib
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path
from .constants import CACHE_VALIDITY_HOURS


# Current cache schema version - increment when cache format changes
CACHE_VERSION = "1.0.0"


class CacheStatistics:
    """Track cache hit/miss statistics and API usage."""

    def __init__(self, stats_file: str):
        self.stats_file = stats_file
        self.stats = self._load_stats()

    def _load_stats(self) -> Dict:
        """Load statistics from file."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load cache statistics: {e}")

        # Default statistics structure
        return {
            "version": CACHE_VERSION,
            "total_hits": 0,
            "total_misses": 0,
            "total_api_calls": 0,
            "by_vendor": {},
            "last_reset": datetime.now().isoformat(),
            "created": datetime.now().isoformat()
        }

    def _save_stats(self):
        """Save statistics to file."""
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache statistics: {e}")

    def record_hit(self, vendor: str = "unknown"):
        """Record a cache hit."""
        self.stats["total_hits"] += 1
        if vendor not in self.stats["by_vendor"]:
            self.stats["by_vendor"][vendor] = {"hits": 0, "misses": 0, "api_calls": 0}
        self.stats["by_vendor"][vendor]["hits"] += 1
        self._save_stats()

    def record_miss(self, vendor: str = "unknown"):
        """Record a cache miss."""
        self.stats["total_misses"] += 1
        if vendor not in self.stats["by_vendor"]:
            self.stats["by_vendor"][vendor] = {"hits": 0, "misses": 0, "api_calls": 0}
        self.stats["by_vendor"][vendor]["misses"] += 1
        self._save_stats()

    def record_api_call(self, vendor: str = "unknown"):
        """Record an API call."""
        self.stats["total_api_calls"] += 1
        if vendor not in self.stats["by_vendor"]:
            self.stats["by_vendor"][vendor] = {"hits": 0, "misses": 0, "api_calls": 0}
        self.stats["by_vendor"][vendor]["api_calls"] += 1
        self._save_stats()

    def get_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        total = self.stats["total_hits"] + self.stats["total_misses"]
        if total == 0:
            return 0.0
        return self.stats["total_hits"] / total

    def get_vendor_hit_rate(self, vendor: str) -> float:
        """Calculate cache hit rate for a specific vendor."""
        if vendor not in self.stats["by_vendor"]:
            return 0.0
        vendor_stats = self.stats["by_vendor"][vendor]
        total = vendor_stats["hits"] + vendor_stats["misses"]
        if total == 0:
            return 0.0
        return vendor_stats["hits"] / total

    def get_summary(self) -> Dict:
        """Get a summary of cache statistics."""
        summary = {
            "overall": {
                "total_hits": self.stats["total_hits"],
                "total_misses": self.stats["total_misses"],
                "total_api_calls": self.stats["total_api_calls"],
                "hit_rate": self.get_hit_rate(),
                "api_calls_saved": self.stats["total_hits"],
            },
            "by_vendor": {}
        }

        for vendor, vendor_stats in self.stats["by_vendor"].items():
            hit_rate = self.get_vendor_hit_rate(vendor)
            summary["by_vendor"][vendor] = {
                "hits": vendor_stats["hits"],
                "misses": vendor_stats["misses"],
                "api_calls": vendor_stats["api_calls"],
                "hit_rate": hit_rate,
            }

        return summary

    def reset(self):
        """Reset all statistics."""
        self.stats = {
            "version": CACHE_VERSION,
            "total_hits": 0,
            "total_misses": 0,
            "total_api_calls": 0,
            "by_vendor": {},
            "last_reset": datetime.now().isoformat(),
            "created": self.stats.get("created", datetime.now().isoformat())
        }
        self._save_stats()


class CacheManager:
    """Manage cache files, cleanup, versioning, and statistics."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Base directory for cache files. If None, uses config default.
        """
        if cache_dir is None:
            from .config import get_config
            config = get_config()
            cache_dir = config["data_cache_dir"]

        self.cache_dir = cache_dir
        self.stats = CacheStatistics(os.path.join(cache_dir, ".cache_stats.json"))
        self.version_file = os.path.join(cache_dir, ".cache_version")

        # Check cache version and invalidate if necessary
        self._check_and_update_version()

    def _check_and_update_version(self):
        """Check cache version and invalidate old caches if version changed."""
        current_version = self._get_current_version()

        if current_version != CACHE_VERSION:
            print(f"Cache version changed ({current_version} -> {CACHE_VERSION}). Invalidating old caches...")
            self.invalidate_all_caches()
            self._set_current_version(CACHE_VERSION)

    def _get_current_version(self) -> str:
        """Get the current cache version from file."""
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r') as f:
                    return f.read().strip()
            except Exception:
                pass
        return "0.0.0"

    def _set_current_version(self, version: str):
        """Set the current cache version."""
        try:
            os.makedirs(os.path.dirname(self.version_file), exist_ok=True)
            with open(self.version_file, 'w') as f:
                f.write(version)
        except Exception as e:
            print(f"Warning: Failed to write cache version: {e}")

    def cleanup_old_cache(
        self,
        retention_hours: Optional[float] = None,
        pattern: str = "*.cache"
    ) -> Tuple[int, int]:
        """
        Remove old cache files based on retention policy.

        Args:
            retention_hours: Maximum age of cache files in hours. If None, uses CACHE_VALIDITY_HOURS * 7
            pattern: Glob pattern for cache files (default: "*.cache")

        Returns:
            Tuple of (files_removed, bytes_freed)
        """
        if retention_hours is None:
            retention_hours = CACHE_VALIDITY_HOURS * 7  # Keep cache for 7x validity period

        retention_seconds = retention_hours * 3600
        current_time = time.time()

        files_removed = 0
        bytes_freed = 0

        # Walk through cache directory and subdirectories
        for root, dirs, files in os.walk(self.cache_dir):
            for filename in files:
                # Skip non-cache files
                if not filename.endswith('.cache') and not filename.endswith('.csv'):
                    continue

                # Skip special files
                if filename.startswith('.cache'):
                    continue

                filepath = os.path.join(root, filename)

                try:
                    file_age = current_time - os.path.getmtime(filepath)

                    if file_age > retention_seconds:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        files_removed += 1
                        bytes_freed += file_size
                        print(f"Removed old cache file: {filename} (age: {file_age/3600:.1f}h)")

                except Exception as e:
                    print(f"Warning: Failed to remove cache file {filename}: {e}")

        return files_removed, bytes_freed

    def invalidate_all_caches(self):
        """Remove all cache files (e.g., on version upgrade)."""
        files_removed = 0

        for root, dirs, files in os.walk(self.cache_dir):
            for filename in files:
                # Only remove cache files, not stats or version files
                if filename.endswith('.cache') or filename.endswith('.csv'):
                    if not filename.startswith('.cache'):
                        filepath = os.path.join(root, filename)
                        try:
                            os.remove(filepath)
                            files_removed += 1
                        except Exception as e:
                            print(f"Warning: Failed to remove cache file {filename}: {e}")

        print(f"Invalidated {files_removed} cache files")
        return files_removed

    def get_cache_info(self) -> Dict:
        """Get information about the cache directory."""
        total_files = 0
        total_size = 0
        cache_files = []

        for root, dirs, files in os.walk(self.cache_dir):
            for filename in files:
                if filename.endswith('.cache') or filename.endswith('.csv'):
                    if not filename.startswith('.cache'):
                        filepath = os.path.join(root, filename)
                        try:
                            file_size = os.path.getsize(filepath)
                            file_age = time.time() - os.path.getmtime(filepath)

                            total_files += 1
                            total_size += file_size

                            cache_files.append({
                                "filename": filename,
                                "path": filepath,
                                "size_bytes": file_size,
                                "age_hours": file_age / 3600,
                                "is_valid": file_age < (CACHE_VALIDITY_HOURS * 3600)
                            })
                        except Exception:
                            pass

        # Sort by age (newest first)
        cache_files.sort(key=lambda x: x["age_hours"])

        return {
            "cache_dir": self.cache_dir,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_version": self._get_current_version(),
            "files": cache_files
        }

    def get_statistics(self) -> Dict:
        """Get cache statistics summary."""
        return self.stats.get_summary()

    def print_statistics(self):
        """Print a formatted summary of cache statistics."""
        stats = self.get_statistics()

        print("\n=== Cache Statistics ===")
        print(f"\nOverall Performance:")
        print(f"  Cache Hits:     {stats['overall']['total_hits']}")
        print(f"  Cache Misses:   {stats['overall']['total_misses']}")
        print(f"  Hit Rate:       {stats['overall']['hit_rate']:.2%}")
        print(f"  API Calls Made: {stats['overall']['total_api_calls']}")
        print(f"  API Calls Saved: {stats['overall']['api_calls_saved']}")

        if stats['by_vendor']:
            print(f"\nBy Vendor:")
            for vendor, vendor_stats in stats['by_vendor'].items():
                print(f"  {vendor}:")
                print(f"    Hits:      {vendor_stats['hits']}")
                print(f"    Misses:    {vendor_stats['misses']}")
                print(f"    Hit Rate:  {vendor_stats['hit_rate']:.2%}")
                print(f"    API Calls: {vendor_stats['api_calls']}")

    def print_cache_info(self):
        """Print formatted cache directory information."""
        info = self.get_cache_info()

        print("\n=== Cache Directory Info ===")
        print(f"Cache Directory: {info['cache_dir']}")
        print(f"Cache Version:   {info['cache_version']}")
        print(f"Total Files:     {info['total_files']}")
        print(f"Total Size:      {info['total_size_mb']:.2f} MB")

        if info['files']:
            print(f"\nCache Files (showing newest 10):")
            for file_info in info['files'][:10]:
                status = "✓ VALID" if file_info['is_valid'] else "✗ STALE"
                print(f"  {status} {file_info['filename']}")
                print(f"    Age: {file_info['age_hours']:.1f}h | Size: {file_info['size_bytes']/1024:.1f} KB")

    def maintenance(self, retention_hours: Optional[float] = None, verbose: bool = True):
        """
        Perform cache maintenance: cleanup old files and print statistics.

        Args:
            retention_hours: Maximum age of cache files in hours
            verbose: Whether to print statistics
        """
        if verbose:
            print("\n=== Running Cache Maintenance ===")

        # Cleanup old cache files
        files_removed, bytes_freed = self.cleanup_old_cache(retention_hours=retention_hours)

        if verbose:
            if files_removed > 0:
                print(f"\nCleaned up {files_removed} old cache files ({bytes_freed/(1024*1024):.2f} MB freed)")
            else:
                print("\nNo old cache files to remove")

            # Print statistics
            self.print_statistics()
            self.print_cache_info()


# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
