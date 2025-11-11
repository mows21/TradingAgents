"""
Shared constants for data flow operations.

These constants are used across multiple data vendors (Y Finance, Alpha Vantage, etc.)
to ensure consistent caching behavior and data fetching strategies.
"""

# Number of years of historical data to fetch for stock data
# Used by: Y Finance, stockstats utilities
HISTORICAL_DATA_YEARS = 15

# Cache validity period in hours
# After this period, cached data is considered stale and will be refreshed
# Used by: Y Finance, Alpha Vantage, and other data vendors
CACHE_VALIDITY_HOURS = 24

# Cache retention period in hours
# After this period, cached files are eligible for deletion during cleanup
# Default: 7 days (7 * 24 = 168 hours)
CACHE_RETENTION_HOURS = 168

# Enable cache statistics tracking
# When enabled, tracks cache hit/miss rates and API usage
CACHE_STATISTICS_ENABLED = True
