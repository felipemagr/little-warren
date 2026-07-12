"""Analysis service: run the rules pipeline over market data and produce Picks.

Pipeline: swings -> waves -> impulse classification (FND) -> 2-4 line trigger
(L24) -> reversal Pick with stop (STP-02), target (L24-04 phase 2) and a
rule-traced confidence score.
"""

from datetime import date, timedelta
from enum import StrEnum

import pandas as pd

from little_warren.application.analysis_service.ports import MarketDataProvider
from little_warren.domain.analysis import detect_swings, segment_waves
from little_warren.domain.entities import Direction, Pick
from little_warren.domain.rules.impulse import ImpulseAssessment, classify_impulse
from little_warren.domain.rules.linea_24 import BreakStatus, LineBreakResult, confirms_fifth_failure, evaluate_linea_24
from little_warren.domain.value_objects.wave import Wave

STOP_OFFSET_FRACTION = 0.02
"""STP-02 places the stop 'slightly beyond' the prior swing extreme without
quantifying the offset (spec gap). CALIBRATED 2026-07 on the dev split: 2%
beat 0.5%/1% across the grid (see docs/calibration-report.md, local)."""

DEFAULT_REVERSAL = 0.04
"""Swing-detection threshold. CALIBRATED 2026-07 on the dev split."""

CONFIDENCE_BASE_CONFIRMED = 0.70
CONFIDENCE_VIOLENT_BONUS = 0.0
CONFIDENCE_FIFTH_FAILURE_BONUS = -0.15
CONFIDENCE_TERMINAL_BONUS = -0.10
CONFIDENCE_EXTENDED_W1_PENALTY = -0.20
CONFIDENCE_CAP = 0.95
CONFIDENCE_FLOOR = 0.05
"""Confidence v1: weights derived from EMPIRICAL dev-set bucket hit rates
(2026-07 calibration): plain confirmed breaks hit ~70-75%; violent breaks add
nothing; fifth-failure, terminal and extended-wave-1 patterns all mark WEAKER
buckets despite the spec's enthusiasm for them. Recalibrate after any change
to entries, stops or filters."""


class EntryMode(StrEnum):
    """How the entry price is set at the confirmed break bar.

    BREAK_CLOSE enters at the break bar's close. LINE_LEVEL assumes a resting
    order at the 2-4 line's price on the break bar (the close crossed the line,
    so the level traded within that bar); it falls back to the break close when
    degenerate geometry would leave the line level beyond the stop.
    """

    BREAK_CLOSE = "break-close"
    LINE_LEVEL = "line-level"


class AnalysisService:
    """Analyse tickers with the codified system and emit reversal Picks."""

    def __init__(
        self,
        provider: MarketDataProvider,
        reversal: float = DEFAULT_REVERSAL,
        freshness_bars: int = 10,
        stop_offset: float = STOP_OFFSET_FRACTION,
        entry_mode: EntryMode | str = EntryMode.LINE_LEVEL,
    ):
        self._provider = provider
        self._reversal = reversal
        self._freshness_bars = freshness_bars
        self._stop_offset = stop_offset
        self._entry_mode = EntryMode(entry_mode)

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
        w5_extreme = waves[4].end.price
        stop = w5_extreme * (1 + self._stop_offset) if impulse_up else w5_extreme * (1 - self._stop_offset)
        entry = self._entry_price(frame, outcome, stop, impulse_up)

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
        if assessment.extended_wave == 1:
            confidence += CONFIDENCE_EXTENDED_W1_PENALTY

        return Pick(
            ticker=ticker,
            as_of=as_of,
            direction=direction,
            entry=entry,
            stop=stop,
            target=target,
            confidence=max(min(confidence, CONFIDENCE_CAP), CONFIDENCE_FLOOR),
            rules_fired=list(dict.fromkeys(rules)),
            evidence={
                "violent": outcome.violent,
                "fifth_failure": fifth_failure,
                "terminal": assessment.is_terminal,
                "extended_wave": assessment.extended_wave,
            },
            notes=outcome.detail,
        )

    def _entry_price(self, frame: pd.DataFrame, outcome: LineBreakResult, stop: float, impulse_up: bool) -> float:
        """Entry per the configured mode.

        LINE_LEVEL fills at the 2-4 line price only when that price actually
        traded within the break bar's range (no fills on gaps through the line)
        and the line sits on the protected side of the stop; otherwise it falls
        back to the break close.
        """
        bar = frame.iloc[outcome.break_index]
        break_close = float(bar["close"])
        if self._entry_mode is EntryMode.BREAK_CLOSE:
            return break_close
        line_level = outcome.line.price_at(outcome.break_index)
        traded = float(bar["low"]) <= line_level <= float(bar["high"])
        protected = line_level < stop if impulse_up else line_level > stop
        return line_level if traded and protected else break_close

    def _target(self, waves: list[Wave], assessment: ImpulseAssessment, fifth_failure: bool) -> tuple[float, str]:
        """L24-04 phase 2: per-pattern minimum retracement requirement."""
        if fifth_failure or assessment.is_terminal:
            return waves[0].start.price, "L24-04"  # full retrace to the pattern origin
        if assessment.extended_wave == 5:
            w5 = waves[4]
            retrace = 0.618 * w5.price_range
            return (w5.end.price - retrace) if waves[0].is_up else (w5.end.price + retrace), "L24-04"
        return waves[3].end.price, "L24-04"  # wave-4 zone (x3 and default)
