"""Segment confirmed swing pivots into waves."""

from little_warren.domain.value_objects.swing import SwingPoint
from little_warren.domain.value_objects.wave import Wave


def segment_waves(pivots: list[SwingPoint]) -> list[Wave]:
    """Build the wave sequence connecting consecutive pivots.

    Pivots must alternate high/low (as produced by `detect_swings`).
    """
    for previous, current in zip(pivots[:-1], pivots[1:], strict=False):
        if previous.kind == current.kind:
            raise ValueError(f"pivots must alternate; got consecutive {current.kind} at indices {current.index}")
    return [Wave(start=a, end=b) for a, b in zip(pivots[:-1], pivots[1:], strict=False)]
