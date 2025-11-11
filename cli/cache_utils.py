#!/usr/bin/env python3
"""
Cache Management Utility for TradingAgents

This script provides command-line utilities to manage the cache system:
- View cache statistics
- Clean up old cache files
- View cache directory information
- Reset cache statistics

Usage:
    python -m cli.cache_utils stats              # Show cache statistics
    python -m cli.cache_utils info               # Show cache directory info
    python -m cli.cache_utils cleanup            # Clean up old cache files
    python -m cli.cache_utils cleanup --hours 48 # Clean up files older than 48 hours
    python -m cli.cache_utils reset-stats        # Reset cache statistics
    python -m cli.cache_utils maintenance        # Run full maintenance (cleanup + stats)
"""

import sys
import argparse
from tradingagents.dataflows.cache_manager import get_cache_manager
from tradingagents.dataflows.constants import CACHE_RETENTION_HOURS


def show_statistics():
    """Display cache statistics."""
    cache_mgr = get_cache_manager()
    cache_mgr.print_statistics()


def show_info():
    """Display cache directory information."""
    cache_mgr = get_cache_manager()
    cache_mgr.print_cache_info()


def cleanup_cache(retention_hours=None):
    """Clean up old cache files."""
    cache_mgr = get_cache_manager()

    if retention_hours is None:
        retention_hours = CACHE_RETENTION_HOURS

    print(f"\n=== Cache Cleanup ===")
    print(f"Removing cache files older than {retention_hours} hours...")

    files_removed, bytes_freed = cache_mgr.cleanup_old_cache(retention_hours=retention_hours)

    if files_removed > 0:
        print(f"\nCleaned up {files_removed} old cache files")
        print(f"Freed {bytes_freed / (1024 * 1024):.2f} MB of disk space")
    else:
        print("\nNo old cache files to remove")


def reset_statistics():
    """Reset cache statistics."""
    cache_mgr = get_cache_manager()

    print("\n=== Resetting Cache Statistics ===")
    cache_mgr.stats.reset()
    print("Cache statistics have been reset")


def run_maintenance(retention_hours=None):
    """Run full cache maintenance."""
    cache_mgr = get_cache_manager()

    if retention_hours is None:
        retention_hours = CACHE_RETENTION_HOURS

    cache_mgr.maintenance(retention_hours=retention_hours, verbose=True)


def main():
    parser = argparse.ArgumentParser(
        description='Cache Management Utility for TradingAgents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats              Show cache statistics
  %(prog)s info               Show cache directory info
  %(prog)s cleanup            Clean up old cache files (default retention: 168 hours)
  %(prog)s cleanup --hours 48 Clean up files older than 48 hours
  %(prog)s reset-stats        Reset cache statistics
  %(prog)s maintenance        Run full maintenance (cleanup + show stats)
        """
    )

    parser.add_argument(
        'command',
        choices=['stats', 'info', 'cleanup', 'reset-stats', 'maintenance'],
        help='Command to run'
    )

    parser.add_argument(
        '--hours',
        type=float,
        default=None,
        help='Retention hours for cleanup (default: from config)'
    )

    args = parser.parse_args()

    try:
        if args.command == 'stats':
            show_statistics()
        elif args.command == 'info':
            show_info()
        elif args.command == 'cleanup':
            cleanup_cache(retention_hours=args.hours)
        elif args.command == 'reset-stats':
            reset_statistics()
        elif args.command == 'maintenance':
            run_maintenance(retention_hours=args.hours)
        else:
            parser.print_help()
            return 1

        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
