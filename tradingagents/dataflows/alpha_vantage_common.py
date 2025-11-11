import os
import requests
import pandas as pd
import json
import time
import hashlib
from datetime import datetime
from io import StringIO
from .constants import CACHE_VALIDITY_HOURS

API_BASE_URL = "https://www.alphavantage.co/query"

def get_api_key() -> str:
    """Retrieve the API key for Alpha Vantage from environment variables."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is not set.")
    return api_key

def format_datetime_for_api(date_input) -> str:
    """Convert various date formats to YYYYMMDDTHHMM format required by Alpha Vantage API."""
    if isinstance(date_input, str):
        # If already in correct format, return as-is
        if len(date_input) == 13 and 'T' in date_input:
            return date_input
        # Try to parse common date formats
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d")
            return dt.strftime("%Y%m%dT0000")
        except ValueError:
            try:
                dt = datetime.strptime(date_input, "%Y-%m-%d %H:%M")
                return dt.strftime("%Y%m%dT%H%M")
            except ValueError:
                raise ValueError(f"Unsupported date format: {date_input}")
    elif isinstance(date_input, datetime):
        return date_input.strftime("%Y%m%dT%H%M")
    else:
        raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")

class AlphaVantageRateLimitError(Exception):
    """Exception raised when Alpha Vantage API rate limit is exceeded."""
    pass

def _get_cache_key(function_name: str, params: dict) -> str:
    """Generate a unique cache key from function name and parameters."""
    # Sort params for consistent hashing
    sorted_params = sorted(params.items())
    cache_string = f"{function_name}:{str(sorted_params)}"
    return hashlib.md5(cache_string.encode()).hexdigest()

def _get_cache_file_path(cache_key: str) -> str:
    """Get the file path for a cache key."""
    from .config import get_config
    config = get_config()
    cache_dir = os.path.join(config["data_cache_dir"], "alphavantage")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{cache_key}.cache")

def _is_cache_valid(cache_file: str) -> bool:
    """Check if cache file exists and is still valid."""
    if not os.path.exists(cache_file):
        return False
    cache_age_seconds = time.time() - os.path.getmtime(cache_file)
    cache_age_hours = cache_age_seconds / 3600
    return cache_age_hours < CACHE_VALIDITY_HOURS

def _make_api_request(function_name: str, params: dict, use_cache: bool = True) -> dict | str:
    """Helper function to make API requests and handle responses with caching.

    Args:
        function_name: Alpha Vantage API function name
        params: Parameters for the API call
        use_cache: Whether to use caching (default: True)

    Raises:
        AlphaVantageRateLimitError: When API rate limit is exceeded
    """
    # Check cache first if caching is enabled
    cache_key = None
    cache_file = None

    if use_cache:
        cache_key = _get_cache_key(function_name, params)
        cache_file = _get_cache_file_path(cache_key)

        if _is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = f.read()
                print(f"DEBUG: Using cached Alpha Vantage data for {function_name}")
                return cached_data
            except Exception as e:
                print(f"Warning: Failed to read cache file: {e}")
                # Continue to make API request

    # Create a copy of params to avoid modifying the original
    api_params = params.copy()
    api_params.update({
        "function": function_name,
        "apikey": get_api_key(),
        "source": "trading_agents",
    })

    # Handle entitlement parameter if present in params or global variable
    current_entitlement = globals().get('_current_entitlement')
    entitlement = api_params.get("entitlement") or current_entitlement

    if entitlement:
        api_params["entitlement"] = entitlement
    elif "entitlement" in api_params:
        # Remove entitlement if it's None or empty
        api_params.pop("entitlement", None)

    try:
        response = requests.get(API_BASE_URL, params=api_params)
        response.raise_for_status()
        response_text = response.text

        # Check if response is JSON (error responses are typically JSON)
        try:
            response_json = json.loads(response_text)
            # Check for rate limit error
            if "Information" in response_json:
                info_message = response_json["Information"]
                if "rate limit" in info_message.lower() or "api key" in info_message.lower():
                    raise AlphaVantageRateLimitError(f"Alpha Vantage rate limit exceeded: {info_message}")
        except json.JSONDecodeError:
            # Response is not JSON (likely CSV data), which is normal
            pass

        # Save to cache if caching is enabled and request was successful
        if use_cache:
            try:
                cache_key = _get_cache_key(function_name, params)
                cache_file = _get_cache_file_path(cache_key)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(response_text)
                print(f"DEBUG: Cached Alpha Vantage data for {function_name}")
            except Exception as e:
                print(f"Warning: Failed to write cache file: {e}")
                # Continue anyway - caching failure shouldn't break functionality

        return response_text

    except AlphaVantageRateLimitError:
        # If we hit rate limit and have stale cache, use it
        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = f.read()
                print(f"WARNING: Rate limit hit, using stale cache for {function_name}")
                return cached_data
            except Exception:
                pass
        # Re-raise if we can't use cache
        raise
    except Exception as e:
        # For other errors, try stale cache as fallback
        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = f.read()
                print(f"WARNING: API request failed ({str(e)}), using stale cache for {function_name}")
                return cached_data
            except Exception:
                pass
        # Re-raise original error if cache fallback fails
        raise



def _filter_csv_by_date_range(csv_data: str, start_date: str, end_date: str) -> str:
    """
    Filter CSV data to include only rows within the specified date range.

    Args:
        csv_data: CSV string from Alpha Vantage API
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Filtered CSV string
    """
    if not csv_data or csv_data.strip() == "":
        return csv_data

    try:
        # Parse CSV data
        df = pd.read_csv(StringIO(csv_data))

        # Assume the first column is the date column (timestamp)
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

        # Filter by date range
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        filtered_df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]

        # Convert back to CSV string
        return filtered_df.to_csv(index=False)

    except Exception as e:
        # If filtering fails, return original data with a warning
        print(f"Warning: Failed to filter CSV data by date range: {e}")
        return csv_data
