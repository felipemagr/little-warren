"""Market data adapter backed by Yahoo Finance (yfinance)."""

from datetime import date

import pandas as pd
import yfinance as yf
from loguru import logger

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class YFinanceProvider:
    """MarketDataProvider adapter fetching OHLCV series from Yahoo Finance."""

    def fetch_ohlcv(self, ticker: str, start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        """Fetch OHLCV for `ticker`, normalized to lowercase standard columns.

        Returns a DataFrame indexed by timestamp with columns open/high/low/close/volume.
        Raises ValueError when Yahoo returns no data (unknown ticker or empty range).
        """
        logger.info("Fetching {} from {} to {} ({})", ticker, start, end, interval)
        raw = yf.download(ticker, start=start, end=end, interval=interval, auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            raise ValueError(f"no data returned for ticker {ticker!r} between {start} and {end}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.rename(columns=str.lower)[OHLCV_COLUMNS]
        frame.index.name = "timestamp"
        return frame
