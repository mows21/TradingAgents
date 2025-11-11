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
