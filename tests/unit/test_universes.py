"""Unit tests for universe loading (stubbed fetchers, no network)."""

import pytest

from little_warren.infrastructure.data.universes import load_index, normalize_symbols

pytestmark = pytest.mark.unit


class TestNormalizeSymbols:
    def test_us_dots_become_dashes(self):
        assert normalize_symbols(["BRK.B", "BF.B", "AAPL"], suffix="") == ["BRK-B", "BF-B", "AAPL"]

    def test_suffix_only_added_when_symbol_has_none(self):
        assert normalize_symbols(["ADS", "BMW.DE", "AIR.PA"], suffix=".DE") == ["ADS.DE", "BMW.DE", "AIR.PA"]

    def test_dedupe_and_junk_dropped(self):
        assert normalize_symbols(["AAPL", "aapl", " ", "nan"], suffix="") == ["AAPL"]


class TestLoadIndex:
    def test_fetch_then_cache(self, tmp_path):
        calls = []

        def fetcher(url, column):
            calls.append(url)
            return ["AAA", "BBB.C"]

        first = load_index("sp500", cache_dir=tmp_path, fetcher=fetcher)
        second = load_index("sp500", cache_dir=tmp_path, fetcher=fetcher)

        assert first == second == ["AAA", "BBB-C"]
        assert len(calls) == 1  # second call served from disk cache

    def test_failure_without_cache_returns_empty(self, tmp_path):
        def broken(url, column):
            raise OSError("offline")

        assert load_index("ftse100", cache_dir=tmp_path, fetcher=broken) == []
