"""Waves: monotonic price legs between consecutive swing pivots."""

from pydantic import BaseModel, ConfigDict, model_validator

from little_warren.domain.value_objects.swing import SwingPoint


class Wave(BaseModel):
    """A price leg from one confirmed pivot to the next.

    Waves are pivot-to-pivot, so the endpoint prices bound the leg's full
    price extent and `duration` is measured in bars.
    """

    model_config = ConfigDict(frozen=True)

    start: SwingPoint
    end: SwingPoint

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "Wave":
        if self.end.index <= self.start.index:
            raise ValueError(f"wave end index {self.end.index} must be after start index {self.start.index}")
        return self

    @property
    def is_up(self) -> bool:
        """True when the leg rises."""
        return self.end.price > self.start.price

    @property
    def price_range(self) -> float:
        """Absolute price travel of the leg."""
        return abs(self.end.price - self.start.price)

    @property
    def duration(self) -> int:
        """Length of the leg in bars."""
        return self.end.index - self.start.index

    @property
    def low(self) -> float:
        return min(self.start.price, self.end.price)

    @property
    def high(self) -> float:
        return max(self.start.price, self.end.price)

    def retracement_of(self, other: "Wave") -> float:
        """This wave's price travel as a fraction of `other`'s (e.g. 0.5 = 50%)."""
        if other.price_range == 0:
            raise ValueError("cannot compute retracement of a zero-range wave")
        return self.price_range / other.price_range
