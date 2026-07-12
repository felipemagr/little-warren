"""Market data adapter backed by Yahoo Finance (yfinance), with an on-disk day cache."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf
from loguru import logger

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
DEFAULT_CACHE_DIR = Path("data/cache/ohlcv")


class YFinanceProvider:
    """MarketDataProvider adapter fetching OHLCV series from Yahoo Finance."""

    def __init__(self, cache_dir: Path | None = DEFAULT_CACHE_DIR):
        self._cache_dir = cache_dir

    def fetch_ohlcv(self, ticker: str, start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        """Fetch OHLCV for `ticker`, normalized to lowercase standard columns.

        Returns a DataFrame indexed by timestamp with columns open/high/low/close/volume.
        Raises ValueError when Yahoo returns no data (unknown ticker or empty range).
        """
        cache_file = self._cache_file(ticker, start, end, interval)
        if cache_file is not None and cache_file.exists():
            return pd.read_pickle(cache_file)

        logger.info("Fetching {} from {} to {} ({})", ticker, start, end, interval)
        raw = yf.download(
            ticker, start=start, end=end, interval=interval, auto_adjust=True, progress=False, timeout=20
        )
        if raw is None or raw.empty:
            raise ValueError(f"no data returned for ticker {ticker!r} between {start} and {end}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        frame = raw.rename(columns=str.lower)[OHLCV_COLUMNS]
        frame.index.name = "timestamp"

        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            frame.to_pickle(cache_file)
        return frame

    def company_name(self, ticker: str) -> str | None:
        """Human-readable company name, cached forever on disk (names do not change)."""
        names_file = self._cache_dir / "names.json" if self._cache_dir else None
        names: dict[str, str | None] = {}
        if names_file is not None and names_file.exists():
            names = json.loads(names_file.read_text())
        key = ticker.upper()
        if key in names:
            return names[key]
        try:
            info = yf.Ticker(ticker).info
            name = info.get("shortName") or info.get("longName")
        except Exception:  # noqa: BLE001
            name = None
        if names_file is not None:
            names_file.parent.mkdir(parents=True, exist_ok=True)
            names[key] = name
            names_file.write_text(json.dumps(names, indent=0, sort_keys=True))
        return name

    def _cache_file(self, ticker: str, start: date, end: date, interval: str) -> Path | None:
        if self._cache_dir is None:
            return None
        safe = "".join(c if c.isalnum() or c in ".-" else "_" for c in ticker.upper())
        pandas_major = pd.__version__.split(".")[0]
        return self._cache_dir / f"{safe}_{interval}_{start}_{end}_pd{pandas_major}.pkl"
