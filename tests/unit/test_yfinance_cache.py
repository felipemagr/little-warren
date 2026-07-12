"""Unit tests for the provider's on-disk cache (stubbed downloads, no network)."""

from datetime import date

import pandas as pd
import pytest

from little_warren.infrastructure.data.yfinance_provider import YFinanceProvider

pytestmark = pytest.mark.unit


def fake_yahoo_frame() -> pd.DataFrame:
    index = pd.bdate_range("2024-01-01", periods=5, name="Date")
    return pd.DataFrame({"Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 1000}, index=index)


class TestProviderCache:
    def test_second_fetch_served_from_disk(self, tmp_path, monkeypatch):
        calls = []

        def fake_download(*args, **kwargs):
            calls.append(args)
            return fake_yahoo_frame()

        monkeypatch.setattr("little_warren.infrastructure.data.yfinance_provider.yf.download", fake_download)
        provider = YFinanceProvider(cache_dir=tmp_path)

        first = provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))
        second = provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))

        assert len(calls) == 1
        pd.testing.assert_frame_equal(first, second)
        assert list(second.columns) == ["open", "high", "low", "close", "volume"]

    def test_different_range_is_a_different_cache_entry(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "little_warren.infrastructure.data.yfinance_provider.yf.download",
            lambda *a, **k: (calls.append(a), fake_yahoo_frame())[1],
        )
        provider = YFinanceProvider(cache_dir=tmp_path)

        provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))
        provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 3, 1))

        assert len(calls) == 2

    def test_cache_disabled_with_none(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "little_warren.infrastructure.data.yfinance_provider.yf.download",
            lambda *a, **k: (calls.append(a), fake_yahoo_frame())[1],
        )
        provider = YFinanceProvider(cache_dir=None)

        provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))
        provider.fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))

        assert len(calls) == 2
        assert list(tmp_path.iterdir()) == []

    def test_weird_ticker_symbols_map_to_safe_filenames(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "little_warren.infrastructure.data.yfinance_provider.yf.download",
            lambda *a, **k: fake_yahoo_frame(),
        )
        provider = YFinanceProvider(cache_dir=tmp_path)

        provider.fetch_ohlcv("^GSPC", start=date(2024, 1, 1), end=date(2024, 2, 1))

        cached = list(tmp_path.iterdir())
        assert len(cached) == 1 and "^" not in cached[0].name
