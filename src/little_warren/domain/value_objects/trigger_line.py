"""Trigger lines: straight lines through two pivots in (bar index, price) space.

The same geometry backs the spec's three signal lines: "2-4" (impulses),
"0-B" (flats/zigzags) and "B-D" (triangles).
"""

from pydantic import BaseModel, ConfigDict, model_validator


class TriggerLine(BaseModel):
    """A signal line anchored at two bars, extendable forward in time."""

    model_config = ConfigDict(frozen=True)

    name: str
    anchor1_index: int
    anchor1_price: float
    anchor2_index: int
    anchor2_price: float

    @model_validator(mode="after")
    def anchors_must_be_distinct_bars(self) -> "TriggerLine":
        if self.anchor2_index <= self.anchor1_index:
            raise ValueError("second anchor must come after the first")
        return self

    @property
    def slope(self) -> float:
        """Price change per bar."""
        return (self.anchor2_price - self.anchor1_price) / (self.anchor2_index - self.anchor1_index)

    def price_at(self, index: int) -> float:
        """The line's price level at a bar index (extrapolates in both directions)."""
        return self.anchor1_price + self.slope * (index - self.anchor1_index)
