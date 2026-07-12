"""Scan service: run the analysis pipeline across a universe of tickers."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from loguru import logger
from pydantic import BaseModel, ConfigDict

from little_warren.application.analysis_service.service import AnalysisService
from little_warren.domain.entities import Pick


class ScanResult(BaseModel):
    """Outcome of scanning a universe at one as-of date."""

    model_config = ConfigDict(frozen=True)

    as_of: date
    scanned: int
    failed: list[str]
    picks: list[Pick]

    def picks_above(self, min_confidence: float) -> list[Pick]:
        return [p for p in self.picks if p.confidence >= min_confidence]


class ScanService:
    """Fan the analysis out over many tickers (I/O-bound: threads)."""

    def __init__(self, analysis: AnalysisService, max_workers: int = 12):
        self._analysis = analysis
        self._max_workers = max_workers

    def scan(
        self,
        tickers: list[str],
        as_of: date,
        lookback_days: int = 730,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ScanResult:
        """Analyse every ticker; failures are collected, never fatal."""
        unique = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
        picks: list[Pick] = []
        failed: list[str] = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._analysis.analyze, t, as_of=as_of, lookback_days=lookback_days): t for t in unique
            }
            for done, future in enumerate(as_completed(futures), start=1):
                ticker = futures[future]
                try:
                    pick = future.result()
                    if pick is not None:
                        picks.append(pick)
                except Exception as error:  # noqa: BLE001 - a bad ticker must not kill the scan
                    logger.warning("scan failed for {}: {}", ticker, error)
                    failed.append(ticker)
                if on_progress:
                    on_progress(done, len(unique))

        picks.sort(key=lambda p: p.confidence, reverse=True)
        return ScanResult(as_of=as_of, scanned=len(unique), failed=sorted(failed), picks=picks)
