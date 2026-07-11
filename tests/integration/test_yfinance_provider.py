"""Integration tests for the yfinance market data adapter (hits the network)."""

from datetime import date

import pytest

from little_warren.infrastructure.data import YFinanceProvider

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_fetch_ohlcv_returns_normalized_frame():
    frame = YFinanceProvider().fetch_ohlcv("AAPL", start=date(2024, 1, 1), end=date(2024, 2, 1))
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert len(frame) > 10
    assert (frame["high"] >= frame["low"]).all()


def test_unknown_ticker_raises():
    with pytest.raises(ValueError, match="no data returned"):
        YFinanceProvider().fetch_ohlcv("THIS-TICKER-DOES-NOT-EXIST-XYZ", start=date(2024, 1, 1), end=date(2024, 2, 1))
