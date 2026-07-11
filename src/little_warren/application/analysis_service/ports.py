"""Ports (Protocols) the analysis service depends on; infrastructure provides adapters."""

from datetime import date
from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    """Source of OHLCV time series for a ticker."""

    def fetch_ohlcv(self, ticker: str, start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        """Return a DataFrame indexed by timestamp with columns: open, high, low, close, volume."""
        ...
