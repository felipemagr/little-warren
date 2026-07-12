"""The Pick entity: the system's final output for one instrument."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Direction(StrEnum):
    """Trade direction."""

    LONG = "long"
    SHORT = "short"


class Pick(BaseModel):
    """A recommended trade produced by the rules engine.

    Every pick must be fully traceable: `rules_fired` lists the spec rule IDs
    that generated it, and `confidence` aggregates only evidence coming from
    those rules.
    """

    ticker: str
    as_of: date
    direction: Direction
    entry: float = Field(gt=0, description="Suggested entry price")
    stop: float = Field(gt=0, description="Stop-loss level mandated by the system")
    target: float | None = Field(default=None, gt=0, description="Price objective, if the fired rules define one")
    confidence: float = Field(ge=0.0, le=1.0, description="Aggregated confidence score in [0, 1]")
    rules_fired: list[str] = Field(min_length=1, description="Spec rule IDs supporting this pick")
    evidence: dict[str, bool | int | None] = Field(
        default_factory=dict, description="Rule-traced evidence flags behind the confidence score"
    )
    notes: str = ""

    @model_validator(mode="after")
    def stop_must_protect_entry(self) -> "Pick":
        """The stop must sit on the losing side of the entry for the trade direction."""
        if self.direction is Direction.LONG and self.stop >= self.entry:
            raise ValueError(f"long pick requires stop < entry (stop={self.stop}, entry={self.entry})")
        if self.direction is Direction.SHORT and self.stop <= self.entry:
            raise ValueError(f"short pick requires stop > entry (stop={self.stop}, entry={self.entry})")
        return self

    @property
    def risk_per_unit(self) -> float:
        """Absolute distance between entry and stop."""
        return abs(self.entry - self.stop)
