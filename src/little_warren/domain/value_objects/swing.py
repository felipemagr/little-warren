"""Swing points: confirmed price pivots used to segment a series into waves."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SwingKind(StrEnum):
    """Whether the pivot is a local top or bottom."""

    HIGH = "high"
    LOW = "low"


class SwingPoint(BaseModel):
    """A confirmed pivot in an OHLCV series.

    `index` is the positional index of the bar in the source frame, so wave
    durations can be measured in bars regardless of calendar gaps.
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    timestamp: datetime
    price: float = Field(gt=0)
    kind: SwingKind
