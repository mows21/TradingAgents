"""
Tests for cache management functionality.

This test suite validates:
- Cache statistics tracking (hits, misses, API calls)
- Cache cleanup functionality
- Cache versioning
- Cache directory management
"""

import os
import tempfile
import shutil
import time
import unittest
from tradingagents.dataflows.cache_manager import CacheManager, CacheStatistics, CACHE_VERSION


class TestCacheStatistics(unittest.TestCase):
    """Test cache statistics tracking."""

    def setUp(self):
        """Create a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.stats_file = os.path.join(self.test_dir, ".cache_stats.json")
        self.stats = CacheStatistics(self.stats_file)

    def tearDown(self):
        """Clean up temporary directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_record_hit(self):
        """Test recording cache hits."""
        self.stats.record_hit("test_vendor")
        self.assertEqual(self.stats.stats["total_hits"], 1)
        self.assertEqual(self.stats.stats["by_vendor"]["test_vendor"]["hits"], 1)

    def test_record_miss(self):
        """Test recording cache misses."""
        self.stats.record_miss("test_vendor")
        self.assertEqual(self.stats.stats["total_misses"], 1)
        self.assertEqual(self.stats.stats["by_vendor"]["test_vendor"]["misses"], 1)

    def test_record_api_call(self):
        """Test recording API calls."""
        self.stats.record_api_call("test_vendor")
        self.assertEqual(self.stats.stats["total_api_calls"], 1)
        self.assertEqual(self.stats.stats["by_vendor"]["test_vendor"]["api_calls"], 1)

    def test_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        self.stats.record_hit("test_vendor")
        self.stats.record_hit("test_vendor")
        self.stats.record_miss("test_vendor")

        # Hit rate should be 2/3 = 0.6667
        self.assertAlmostEqual(self.stats.get_hit_rate(), 2/3, places=4)
        self.assertAlmostEqual(self.stats.get_vendor_hit_rate("test_vendor"), 2/3, places=4)

    def test_statistics_persistence(self):
        """Test that statistics are persisted to disk."""
        self.stats.record_hit("test_vendor")
        self.stats.record_miss("test_vendor")

        # Create a new statistics object reading the same file
        new_stats = CacheStatistics(self.stats_file)
        self.assertEqual(new_stats.stats["total_hits"], 1)
        self.assertEqual(new_stats.stats["total_misses"], 1)

    def test_reset(self):
        """Test resetting statistics."""
        self.stats.record_hit("test_vendor")
        self.stats.record_miss("test_vendor")
        self.stats.reset()

        self.assertEqual(self.stats.stats["total_hits"], 0)
        self.assertEqual(self.stats.stats["total_misses"], 0)

    def test_get_summary(self):
        """Test statistics summary generation."""
        self.stats.record_hit("vendor1")
        self.stats.record_miss("vendor1")
        self.stats.record_api_call("vendor1")
        self.stats.record_hit("vendor2")

        summary = self.stats.get_summary()

        self.assertEqual(summary["overall"]["total_hits"], 2)
        self.assertEqual(summary["overall"]["total_misses"], 1)
        self.assertEqual(summary["overall"]["total_api_calls"], 1)
        self.assertAlmostEqual(summary["overall"]["hit_rate"], 2/3, places=4)

        self.assertIn("vendor1", summary["by_vendor"])
        self.assertIn("vendor2", summary["by_vendor"])


class TestCacheManager(unittest.TestCase):
    """Test cache manager functionality."""

    def setUp(self):
        """Create a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.cache_mgr = CacheManager(cache_dir=self.test_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_cache_versioning(self):
        """Test cache version checking."""
        version = self.cache_mgr._get_current_version()
        self.assertEqual(version, CACHE_VERSION)

    def test_cleanup_old_cache(self):
        """Test cleaning up old cache files."""
        # Create some test cache files with different ages
        test_files = [
            "test1.cache",
            "test2.cache",
            "test3.csv"
        ]

        for filename in test_files:
            filepath = os.path.join(self.test_dir, filename)
            with open(filepath, 'w') as f:
                f.write("test data")

        # Make one file old by modifying its timestamp
        old_file = os.path.join(self.test_dir, "test1.cache")
        old_time = time.time() - (200 * 3600)  # 200 hours old
        os.utime(old_file, (old_time, old_time))

        # Clean up files older than 100 hours
        files_removed, bytes_freed = self.cache_mgr.cleanup_old_cache(retention_hours=100)

        # Should have removed only the old file
        self.assertEqual(files_removed, 1)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test2.cache")))

    def test_get_cache_info(self):
        """Test getting cache directory information."""
        # Create some test cache files
        for i in range(3):
            filepath = os.path.join(self.test_dir, f"test{i}.cache")
            with open(filepath, 'w') as f:
                f.write("test data " * 100)

        info = self.cache_mgr.get_cache_info()

        self.assertEqual(info["total_files"], 3)
        self.assertGreater(info["total_size_bytes"], 0)
        self.assertEqual(len(info["files"]), 3)

    def test_invalidate_all_caches(self):
        """Test invalidating all cache files."""
        # Create some test cache files
        for i in range(3):
            filepath = os.path.join(self.test_dir, f"test{i}.cache")
            with open(filepath, 'w') as f:
                f.write("test data")

        files_removed = self.cache_mgr.invalidate_all_caches()
        self.assertEqual(files_removed, 3)

        # Verify all cache files are gone
        remaining_files = [f for f in os.listdir(self.test_dir)
                          if f.endswith('.cache') or f.endswith('.csv')]
        # Filter out special files
        remaining_files = [f for f in remaining_files if not f.startswith('.cache')]
        self.assertEqual(len(remaining_files), 0)

    def test_statistics_integration(self):
        """Test that cache manager properly integrates with statistics."""
        self.cache_mgr.stats.record_hit("test_vendor")
        summary = self.cache_mgr.get_statistics()

        self.assertEqual(summary["overall"]["total_hits"], 1)


class TestCacheManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Create a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.cache_mgr = CacheManager(cache_dir=self.test_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_empty_cache_directory(self):
        """Test handling of empty cache directory."""
        info = self.cache_mgr.get_cache_info()
        self.assertEqual(info["total_files"], 0)
        self.assertEqual(info["total_size_bytes"], 0)

    def test_cleanup_empty_directory(self):
        """Test cleanup with no files to remove."""
        files_removed, bytes_freed = self.cache_mgr.cleanup_old_cache(retention_hours=100)
        self.assertEqual(files_removed, 0)
        self.assertEqual(bytes_freed, 0)

    def test_hit_rate_with_no_data(self):
        """Test hit rate calculation with no data."""
        hit_rate = self.cache_mgr.stats.get_hit_rate()
        self.assertEqual(hit_rate, 0.0)

    def test_vendor_hit_rate_nonexistent(self):
        """Test vendor hit rate for non-existent vendor."""
        hit_rate = self.cache_mgr.stats.get_vendor_hit_rate("nonexistent_vendor")
        self.assertEqual(hit_rate, 0.0)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
