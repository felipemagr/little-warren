"""Builders for synthetic OHLCV frames used in rule unit tests.

Fixtures are functions, not static files, so tests can construct patterns with
exact boundary values (e.g. a retracement of precisely 61.8%).
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from little_warren.domain.value_objects.swing import SwingKind, SwingPoint
from little_warren.domain.value_objects.wave import Wave


def bars_from_waypoints(waypoints: list[float], bars_per_leg: int = 5, start: str = "2024-01-01") -> pd.DataFrame:
    """Build an OHLCV frame whose price travels linearly through `waypoints`.

    Each consecutive pair of waypoints becomes one leg of `bars_per_leg` bars.
    Bars are degenerate (open=high=low=close) so pivot prices land exactly on
    the waypoints, making assertions deterministic.
    """
    if len(waypoints) < 2:
        raise ValueError("need at least two waypoints")
    closes: list[float] = []
    for leg_start, leg_end in zip(waypoints[:-1], waypoints[1:], strict=True):
        leg = np.linspace(leg_start, leg_end, bars_per_leg + 1)[:-1]
        closes.extend(leg.tolist())
    closes.append(waypoints[-1])

    index = pd.bdate_range(start=start, periods=len(closes), name="timestamp")
    prices = pd.Series(closes, index=index)
    return pd.DataFrame(
        {"open": prices, "high": prices, "low": prices, "close": prices, "volume": 1_000_000},
    )


def waves_from_prices(prices: list[float], bars_per_leg: int | list[int] = 5) -> list[Wave]:
    """Build a wave sequence whose pivots sit exactly on `prices`.

    `bars_per_leg` sets each wave's duration in bars; pass a list to give legs
    different durations (e.g. to violate time alternation deliberately).
    """
    if len(prices) < 2:
        raise ValueError("need at least two prices")
    durations = [bars_per_leg] * (len(prices) - 1) if isinstance(bars_per_leg, int) else bars_per_leg
    if len(durations) != len(prices) - 1:
        raise ValueError("bars_per_leg list must have len(prices) - 1 entries")

    pivots: list[SwingPoint] = []
    index = 0
    base = datetime(2024, 1, 1)
    for position, price in enumerate(prices):
        if position > 0:
            index += durations[position - 1]
        kind = SwingKind.LOW if _is_local_low(prices, position) else SwingKind.HIGH
        pivots.append(SwingPoint(index=index, timestamp=base + timedelta(days=index), price=price, kind=kind))
    return [Wave(start=a, end=b) for a, b in zip(pivots[:-1], pivots[1:], strict=False)]


def _is_local_low(prices: list[float], position: int) -> bool:
    if position == 0:
        return prices[1] > prices[0]
    return prices[position] < prices[position - 1]
