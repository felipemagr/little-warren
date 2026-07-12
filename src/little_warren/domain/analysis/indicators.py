"""Momentum indicators used as entry filters (IND/ENT sections of the spec)."""

import pandas as pd

STOCHASTIC_PERIOD = 14
STOCHASTIC_SMOOTH = 3
"""ASSUMED (spec gap): the spec prescribes stochastic thresholds (ENT-COR-03)
but never the %K/%D periods; 14/3 slow %K is the industry standard."""


def stochastic_k(frame: pd.DataFrame, period: int = STOCHASTIC_PERIOD, smooth: int = STOCHASTIC_SMOOTH) -> pd.Series:
    """Slow stochastic %K in [0, 100]; NaN until enough bars exist."""
    lowest = frame["low"].rolling(period).min()
    highest = frame["high"].rolling(period).max()
    span = (highest - lowest).replace(0, float("nan"))
    raw = 100 * (frame["close"] - lowest) / span
    return raw.rolling(smooth).mean()


def stochastic_k_at(frame: pd.DataFrame, index: int) -> float | None:
    """Daily slow %K at a bar, using only data up to that bar (no look-ahead)."""
    visible = frame.iloc[: index + 1]
    value = stochastic_k(visible).iloc[-1]
    return None if pd.isna(value) else float(value)


def weekly_stochastic_k_at(frame: pd.DataFrame, index: int) -> float | None:
    """Weekly slow %K at a bar, resampling only the bars up to that bar."""
    visible = frame.iloc[: index + 1]
    weekly = visible.resample("W-FRI").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    if len(weekly) < STOCHASTIC_PERIOD + STOCHASTIC_SMOOTH:
        return None
    value = stochastic_k(weekly).iloc[-1]
    return None if pd.isna(value) else float(value)
