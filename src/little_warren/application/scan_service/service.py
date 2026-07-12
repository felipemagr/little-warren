"""Scan service: run the analysis pipeline across a universe of tickers."""

import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
        timeout_seconds: float = 900.0,
    ) -> ScanResult:
        """Analyse every ticker; failures are collected, never fatal."""
        unique = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
        picks: list[Pick] = []
        failed: list[str] = []
        deadline = time.monotonic() + timeout_seconds

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._analysis.analyze, t, as_of=as_of, lookback_days=lookback_days): t for t in unique
            }
            pending = set(futures)
            completed = 0
            while pending:
                done, pending = wait(pending, timeout=10.0, return_when=FIRST_COMPLETED)
                for future in done:
                    ticker = futures[future]
                    completed += 1
                    try:
                        pick = future.result()
                        if pick is not None:
                            picks.append(pick)
                    except Exception as error:  # noqa: BLE001
                        logger.warning("scan failed for {}: {}", ticker, error)
                        failed.append(ticker)
                    if on_progress:
                        on_progress(completed, len(unique))
                if pending and time.monotonic() > deadline:
                    stragglers = sorted(futures[f] for f in pending)
                    logger.warning("scan deadline reached; abandoning {} tickers: {}", len(stragglers), stragglers)
                    for future in pending:
                        future.cancel()
                    failed.extend(stragglers)
                    break

        picks.sort(key=lambda p: p.confidence, reverse=True)
        return ScanResult(as_of=as_of, scanned=len(unique), failed=sorted(failed), picks=picks)
