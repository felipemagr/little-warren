"""Builders for synthetic OHLCV frames used in rule unit tests.

Fixtures are functions, not static files, so tests can construct patterns with
exact boundary values (e.g. a retracement of precisely 61.8%).
"""

import numpy as np
import pandas as pd


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
