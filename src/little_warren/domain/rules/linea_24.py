"""The "línea 2-4" trigger mechanism: the spec's master signal (L24 section).

Given a classified five-wave impulse and the bars that follow it, this module
builds the 2-4 line (L24-01), checks its validity (L24-02), detects the
confirming break with the tr <= t5 time condition (L24-03), diagnoses slow
breaks (L24-05) and confirms the violent-break fifth-failure variant (L24-09).
"""

from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from little_warren.domain.value_objects.trigger_line import TriggerLine
from little_warren.domain.value_objects.wave import Wave

VIOLENCE_FACTOR = 1.5
"""ASSUMED (spec gap): a break is 'violent' when the break bar's true range is at
least this multiple of the mean true range over the preceding wave-5 window.
The spec never quantifies 'violento'; tune via backtest."""


class BreakStatus(StrEnum):
    """Outcome of watching the 2-4 line after wave 5."""

    INVALID_LINE = "invalid_line"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SLOW = "slow"


class LineBreakResult(BaseModel):
    """What the 2-4 line said about the end of the impulse."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    status: BreakStatus
    line: TriggerLine
    break_index: int | None
    tr: int | None
    t5: int
    violent: bool
    rules_applied: list[str]
    detail: str


def build_linea_24(waves: list[Wave]) -> TriggerLine:
    """L24-01: the line joining the end of wave 2 with the end of wave 4."""
    if len(waves) != 5:
        raise ValueError(f"need the 5 impulse waves, got {len(waves)}")
    w2, w4 = waves[1], waves[3]
    return TriggerLine(
        name="2-4",
        anchor1_index=w2.end.index,
        anchor1_price=w2.end.price,
        anchor2_index=w4.end.index,
        anchor2_price=w4.end.price,
    )


def evaluate_linea_24(
    frame: pd.DataFrame,
    waves: list[Wave],
    violence_factor: float = VIOLENCE_FACTOR,
) -> LineBreakResult:
    """Watch the 2-4 line from the end of wave 5 and classify what happened.

    `frame` must be the OHLCV frame the waves were detected on (positional
    indices aligned). Break = first bar after wave 5 whose CLOSE crosses the
    line (close chosen over intrabar extremes to avoid noise; interpretive
    choice, the spec does not specify the crossing price).
    """
    line = build_linea_24(waves)
    trend_up = waves[0].is_up
    w5 = waves[4]
    t5 = w5.duration

    validity_problem = _validity_problem(frame, waves, line, trend_up)
    if validity_problem:
        return _result(BreakStatus.INVALID_LINE, line, None, None, t5, False, ["L24-01", "L24-02"], validity_problem)

    closes = frame["close"].to_numpy()
    break_index = _first_cross(closes, line, start=w5.end.index + 1, trend_up=trend_up)
    if break_index is None:
        detail = "no close beyond the line yet; trend persists while the line holds (L24-07)"
        return _result(BreakStatus.PENDING, line, None, None, t5, False, ["L24-01", "L24-02", "L24-07"], detail)

    tr = break_index - w5.end.index
    violent = _is_violent(frame, break_index, window=t5, factor=violence_factor)

    if tr <= t5:
        detail = f"line pierced in tr={tr} bars <= t5={t5}: impulse conclusion confirmed"
        return _result(
            BreakStatus.CONFIRMED, line, break_index, tr, t5, violent, ["L24-01", "L24-02", "L24-03"], detail
        )
    detail = (
        f"line pierced in tr={tr} bars > t5={t5}: wave 5 may be terminal, wave 4 unfinished, "
        "or the count is wrong; re-label rather than fight the market"
    )
    return _result(BreakStatus.SLOW, line, break_index, tr, t5, violent, ["L24-01", "L24-02", "L24-05"], detail)


def confirms_fifth_failure(waves: list[Wave], outcome: LineBreakResult) -> bool:
    """L24-09: violent perforation while wave 5 never surpassed the end of wave 3."""
    if outcome.break_index is None or not outcome.violent:
        return False
    w3, w5 = waves[2], waves[4]
    trend_up = waves[0].is_up
    wave5_exceeded_wave3 = w5.end.price > w3.end.price if trend_up else w5.end.price < w3.end.price
    return not wave5_exceeded_wave3


def _validity_problem(frame: pd.DataFrame, waves: list[Wave], line: TriggerLine, trend_up: bool) -> str | None:
    """L24-02: no part of wave 3 or wave 5 may pierce the line while the pattern unfolds."""
    for label, wave in (("3", waves[2]), ("5", waves[4])):
        segment = frame.iloc[wave.start.index : wave.end.index + 1]
        for offset, (_, bar) in enumerate(segment.iterrows()):
            index = wave.start.index + offset
            level = line.price_at(index)
            pierced = bar["low"] < level if trend_up else bar["high"] > level
            if pierced:
                return f"wave {label} pierces the 2-4 line at bar {index}: line or count invalid"
    return None


def _first_cross(closes, line: TriggerLine, start: int, trend_up: bool) -> int | None:
    for index in range(start, len(closes)):
        level = line.price_at(index)
        crossed = closes[index] < level if trend_up else closes[index] > level
        if crossed:
            return index
    return None


def _is_violent(frame: pd.DataFrame, break_index: int, window: int, factor: float) -> bool:
    """ASSUMED quantification of 'violent': break-bar true range vs the recent mean."""
    true_ranges = _true_ranges(frame)
    window = max(window, 3)
    start = max(break_index - window, 1)
    reference = true_ranges[start:break_index]
    if len(reference) == 0 or reference.mean() == 0:
        return False
    return true_ranges[break_index] >= factor * reference.mean()


def _true_ranges(frame: pd.DataFrame):
    high, low, close = (frame[column].to_numpy() for column in ("high", "low", "close"))
    previous_close = pd.Series(close).shift(1).to_numpy()
    ranges = pd.DataFrame(
        {
            "hl": high - low,
            "hc": abs(high - previous_close),
            "lc": abs(low - previous_close),
        }
    )
    return ranges.max(axis=1).to_numpy()


def _result(
    status: BreakStatus,
    line: TriggerLine,
    break_index: int | None,
    tr: int | None,
    t5: int,
    violent: bool,
    rules: list[str],
    detail: str,
) -> LineBreakResult:
    return LineBreakResult(
        status=status,
        line=line,
        break_index=break_index,
        tr=tr,
        t5=t5,
        violent=violent,
        rules_applied=rules,
        detail=detail,
    )
