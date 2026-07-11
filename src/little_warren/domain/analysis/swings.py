"""Zigzag swing detection: segment an OHLCV series into alternating pivots."""

import pandas as pd

from little_warren.domain.value_objects.swing import SwingKind, SwingPoint

REQUIRED_COLUMNS = ("high", "low")


def detect_swings(frame: pd.DataFrame, reversal: float = 0.05) -> list[SwingPoint]:
    """Detect confirmed swing pivots with a fractional reversal threshold.

    A swing high is confirmed once price falls at least `reversal` (e.g. 0.05 = 5%)
    from the running maximum high; a swing low mirrors it. Pivots alternate
    high/low by construction. The still-forming extreme at the end of the series
    is NOT returned: only confirmed pivots.

    Args:
        frame: OHLCV frame with `high` and `low` columns, ordered by time.
        reversal: fractional counter-move that confirms a pivot; must be > 0.

    Returns:
        Confirmed pivots in chronological order.
    """
    if reversal <= 0:
        raise ValueError(f"reversal must be > 0, got {reversal}")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"frame is missing required columns: {missing}")
    if len(frame) < 2:
        return []

    highs = frame["high"].to_numpy()
    lows = frame["low"].to_numpy()
    timestamps = frame.index

    pivots: list[SwingPoint] = []
    direction: SwingKind | None = None
    extreme_high, extreme_high_index = highs[0], 0
    extreme_low, extreme_low_index = lows[0], 0

    for i in range(1, len(frame)):
        if direction is None:
            # Undecided start: wait for the first reversal-sized move to pick a direction.
            if highs[i] > extreme_high:
                extreme_high, extreme_high_index = highs[i], i
            if lows[i] < extreme_low:
                extreme_low, extreme_low_index = lows[i], i
            if highs[i] >= extreme_low * (1 + reversal):
                pivots.append(_pivot(timestamps, extreme_low_index, extreme_low, SwingKind.LOW))
                direction = SwingKind.HIGH
                extreme_high, extreme_high_index = highs[i], i
            elif lows[i] <= extreme_high * (1 - reversal):
                pivots.append(_pivot(timestamps, extreme_high_index, extreme_high, SwingKind.HIGH))
                direction = SwingKind.LOW
                extreme_low, extreme_low_index = lows[i], i
        elif direction is SwingKind.HIGH:
            # Rising leg: extend the running top or confirm it on a sufficient drop.
            if highs[i] > extreme_high:
                extreme_high, extreme_high_index = highs[i], i
            elif lows[i] <= extreme_high * (1 - reversal):
                pivots.append(_pivot(timestamps, extreme_high_index, extreme_high, SwingKind.HIGH))
                direction = SwingKind.LOW
                extreme_low, extreme_low_index = lows[i], i
        else:
            # Falling leg: extend the running bottom or confirm it on a sufficient rally.
            if lows[i] < extreme_low:
                extreme_low, extreme_low_index = lows[i], i
            elif highs[i] >= extreme_low * (1 + reversal):
                pivots.append(_pivot(timestamps, extreme_low_index, extreme_low, SwingKind.LOW))
                direction = SwingKind.HIGH
                extreme_high, extreme_high_index = highs[i], i

    return pivots


def _pivot(timestamps: pd.Index, index: int, price: float, kind: SwingKind) -> SwingPoint:
    return SwingPoint(index=index, timestamp=timestamps[index], price=float(price), kind=kind)
