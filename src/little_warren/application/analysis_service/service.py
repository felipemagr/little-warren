"""Analysis service: run the rules pipeline over market data and produce Picks.

Pipeline: swings -> waves -> impulse classification (FND) -> 2-4 line trigger
(L24) -> reversal Pick with stop (STP-02), target (L24-04 phase 2) and a
rule-traced confidence score.
"""

from datetime import date, timedelta

import pandas as pd

from little_warren.application.analysis_service.ports import MarketDataProvider
from little_warren.domain.analysis import detect_swings, segment_waves
from little_warren.domain.entities import Direction, Pick
from little_warren.domain.rules.impulse import ImpulseAssessment, classify_impulse
from little_warren.domain.rules.linea_24 import BreakStatus, LineBreakResult, confirms_fifth_failure, evaluate_linea_24
from little_warren.domain.value_objects.wave import Wave

STOP_OFFSET_FRACTION = 0.005
"""ASSUMED (spec gap): STP-02 places the stop 'slightly beyond' the prior swing
extreme without quantifying the offset. Default 0.5%; tune via backtest."""

CONFIDENCE_BASE_CONFIRMED = 0.5
CONFIDENCE_VIOLENT_BONUS = 0.15
CONFIDENCE_FIFTH_FAILURE_BONUS = 0.15
CONFIDENCE_TERMINAL_BONUS = 0.10
CONFIDENCE_CAP = 0.95
"""Confidence v0: heuristic weights over rule-traced evidence (CONFIRMED break =
the spec's 'most reliable signal'; fifth failure and terminal patterns carry a
minimum-move guarantee to the pattern origin). Calibrate against backtests."""


class AnalysisService:
    """Analyse tickers with the codified system and emit reversal Picks."""

    def __init__(self, provider: MarketDataProvider, reversal: float = 0.05, freshness_bars: int = 10):
        self._provider = provider
        self._reversal = reversal
        self._freshness_bars = freshness_bars

    def analyze(self, ticker: str, as_of: date, lookback_days: int = 730, interval: str = "1d") -> Pick | None:
        """Fetch data up to `as_of` and analyse it (no look-ahead beyond as_of)."""
        start = as_of - timedelta(days=lookback_days)
        frame = self._provider.fetch_ohlcv(ticker, start=start, end=as_of, interval=interval)
        return self.analyze_frame(frame, ticker=ticker, as_of=as_of)

    def analyze_frame(self, frame: pd.DataFrame, ticker: str, as_of: date) -> Pick | None:
        """Run the pipeline on an OHLCV frame; return the freshest actionable Pick, if any."""
        pivots = detect_swings(frame, reversal=self._reversal)
        if len(pivots) < 6:
            return None

        for start in range(len(pivots) - 6, -1, -1):
            waves = segment_waves(pivots[start : start + 6])
            assessment = classify_impulse(waves)
            if not assessment.is_impulse:
                continue
            outcome = evaluate_linea_24(frame, waves)
            if outcome.status is not BreakStatus.CONFIRMED:
                continue
            if (len(frame) - 1) - outcome.break_index > self._freshness_bars:
                continue
            return self._build_pick(frame, waves, assessment, outcome, ticker, as_of)
        return None

    def _build_pick(
        self,
        frame: pd.DataFrame,
        waves: list[Wave],
        assessment: ImpulseAssessment,
        outcome: LineBreakResult,
        ticker: str,
        as_of: date,
    ) -> Pick:
        """The confirmed 2-4 break trades AGAINST the concluded impulse (L24-03)."""
        impulse_up = waves[0].is_up
        direction = Direction.SHORT if impulse_up else Direction.LONG
        entry = float(frame["close"].iloc[outcome.break_index])
        w5_extreme = waves[4].end.price
        stop = w5_extreme * (1 + STOP_OFFSET_FRACTION) if impulse_up else w5_extreme * (1 - STOP_OFFSET_FRACTION)

        fifth_failure = confirms_fifth_failure(waves, outcome)
        target, target_rule = self._target(waves, assessment, fifth_failure)

        rules = ["FND-10", *outcome.rules_applied, "STP-02", target_rule]
        confidence = CONFIDENCE_BASE_CONFIRMED
        if outcome.violent:
            confidence += CONFIDENCE_VIOLENT_BONUS
        if fifth_failure:
            confidence += CONFIDENCE_FIFTH_FAILURE_BONUS
            rules.append("L24-09")
        if assessment.is_terminal:
            confidence += CONFIDENCE_TERMINAL_BONUS
            rules.append("PAT-TER-01")

        return Pick(
            ticker=ticker,
            as_of=as_of,
            direction=direction,
            entry=entry,
            stop=stop,
            target=target,
            confidence=min(confidence, CONFIDENCE_CAP),
            rules_fired=list(dict.fromkeys(rules)),
            notes=outcome.detail,
        )

    def _target(self, waves: list[Wave], assessment: ImpulseAssessment, fifth_failure: bool) -> tuple[float, str]:
        """L24-04 phase 2: per-pattern minimum retracement requirement."""
        if fifth_failure or assessment.is_terminal:
            return waves[0].start.price, "L24-04"  # full retrace to the pattern origin
        if assessment.extended_wave == 5:
            w5 = waves[4]
            retrace = 0.618 * w5.price_range
            return (w5.end.price - retrace) if waves[0].is_up else (w5.end.price + retrace), "L24-04"
        return waves[3].end.price, "L24-04"  # wave-4 zone (x3 and default)
