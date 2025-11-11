import pandas as pd
import yfinance as yf
from stockstats import wrap
from typing import Annotated
import os
import time
from .config import get_config, DATA_DIR
from .constants import HISTORICAL_DATA_YEARS, CACHE_VALIDITY_HOURS


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        # Get config and set up data directory path
        config = get_config()
        online = config["data_vendors"]["technical_indicators"] != "local"

        df = None
        data = None

        if not online:
            try:
                data = pd.read_csv(
                    os.path.join(
                        DATA_DIR,
                        f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                    )
                )
                df = wrap(data)
            except FileNotFoundError:
                raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
        else:
            # Get today's date as YYYY-mm-dd to add to cache
            today_date = pd.Timestamp.today()
            curr_date_dt = pd.to_datetime(curr_date)

            end_date = today_date
            start_date = today_date - pd.DateOffset(years=HISTORICAL_DATA_YEARS)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Get config and ensure cache directory exists
            os.makedirs(config["data_cache_dir"], exist_ok=True)

            # Use static cache filename for better cache reuse
            data_file = os.path.join(
                config["data_cache_dir"],
                f"{symbol}-YFin-data-cache.csv",
            )

            # Check if cache exists and is still valid
            cache_valid = False
            if os.path.exists(data_file):
                cache_age_seconds = time.time() - os.path.getmtime(data_file)
                cache_age_hours = cache_age_seconds / 3600
                cache_valid = cache_age_hours < CACHE_VALIDITY_HOURS

            if cache_valid:
                # Use cached data
                data = pd.read_csv(data_file)
                data["Date"] = pd.to_datetime(data["Date"])
            else:
                # Fetch fresh data with error handling
                try:
                    data = yf.download(
                        symbol,
                        start=start_date_str,
                        end=end_date_str,
                        multi_level_index=False,
                        progress=False,
                        auto_adjust=True,
                    )

                    if data.empty:
                        raise Exception(f"No data returned for symbol '{symbol}'")

                    data = data.reset_index()
                    data.to_csv(data_file, index=False)

                except Exception as e:
                    # If download fails but we have stale cache, use it with a warning
                    if os.path.exists(data_file):
                        print(f"Warning: Failed to fetch fresh data ({str(e)}), using stale cache")
                        data = pd.read_csv(data_file)
                        data["Date"] = pd.to_datetime(data["Date"])
                    else:
                        raise Exception(f"Failed to download data for {symbol}: {str(e)}")

            df = wrap(data)
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            curr_date = curr_date_dt.strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
