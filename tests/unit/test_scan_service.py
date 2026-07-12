"""Unit tests for the scan service (stubbed analysis, no network)."""

from datetime import date

import pytest

from little_warren.application.scan_service import ScanService
from little_warren.domain.entities import Direction, Pick

pytestmark = pytest.mark.unit

AS_OF = date(2024, 6, 1)


def make_pick(ticker: str, confidence: float) -> Pick:
    return Pick(
        ticker=ticker,
        as_of=AS_OF,
        direction=Direction.LONG,
        entry=100.0,
        stop=95.0,
        confidence=confidence,
        rules_fired=["R-001"],
    )


class StubAnalysis:
    """Analysis double: returns a pick, nothing, or blows up per ticker."""

    def analyze(self, ticker: str, as_of: date, lookback_days: int = 730, interval: str = "1d") -> Pick | None:
        if ticker == "GOOD":
            return make_pick(ticker, 0.70)
        if ticker == "BETTER":
            return make_pick(ticker, 0.85)
        if ticker == "BROKEN":
            raise ValueError("no data")
        return None


class TestScanService:
    def test_scan_collects_sorts_and_survives_failures(self):
        service = ScanService(StubAnalysis(), max_workers=2)

        result = service.scan(["GOOD", "QUIET", "BROKEN", "BETTER"], as_of=AS_OF)

        assert result.scanned == 4
        assert result.failed == ["BROKEN"]
        assert [p.ticker for p in result.picks] == ["BETTER", "GOOD"]  # sorted by confidence

    def test_picks_above_threshold(self):
        service = ScanService(StubAnalysis(), max_workers=2)

        result = service.scan(["GOOD", "BETTER"], as_of=AS_OF)

        assert [p.ticker for p in result.picks_above(0.80)] == ["BETTER"]

    def test_deadline_marks_stragglers_failed(self):
        import time

        class SlowAnalysis:
            def analyze(self, ticker, as_of, lookback_days=730, interval="1d"):
                time.sleep(0.2)
                return make_pick(ticker, 0.7)

        service = ScanService(SlowAnalysis(), max_workers=1)

        result = service.scan(["T0", "T1", "T2", "T3"], as_of=AS_OF, timeout_seconds=0.05)

        assert len(result.picks) >= 1
        assert len(result.picks) + len(result.failed) == 4
        assert "T3" in result.failed

    def test_tickers_deduplicated_and_normalized(self):
        service = ScanService(StubAnalysis(), max_workers=2)

        result = service.scan([" good ", "GOOD", "good"], as_of=AS_OF)

        assert result.scanned == 1
        assert len(result.picks) == 1
