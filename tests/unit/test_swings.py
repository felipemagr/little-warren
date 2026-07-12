"""Unit tests for zigzag swing detection."""

import pytest

from little_warren.domain.analysis import detect_swings
from little_warren.domain.value_objects.swing import SwingKind
from tests.fixtures.synthetic import bars_from_waypoints

pytestmark = pytest.mark.unit


class TestDetectSwings:
    def test_detects_interior_waypoints_as_alternating_pivots(self):
        frame = bars_from_waypoints([100, 130, 110, 140, 120])

        pivots = detect_swings(frame, reversal=0.05)

        # First and last waypoints are unconfirmed ends; interior extremes are pivots.
        assert [p.kind for p in pivots] == [SwingKind.LOW, SwingKind.HIGH, SwingKind.LOW, SwingKind.HIGH]
        assert [p.price for p in pivots] == [100, 130, 110, 140]

    def test_oscillation_below_threshold_yields_no_pivots(self):
        frame = bars_from_waypoints([100, 102, 100, 102, 100])

        assert detect_swings(frame, reversal=0.05) == []

    def test_reversal_exactly_at_threshold_confirms_pivot(self):
        frame = bars_from_waypoints([100, 120, 114])  # 5% drop from 120

        pivots = detect_swings(frame, reversal=0.05)

        assert [p.price for p in pivots] == [100, 120]

    def test_reversal_just_below_threshold_does_not_confirm(self):
        frame = bars_from_waypoints([100, 120, 114.5])  # 4.58% drop from 120

        pivots = detect_swings(frame, reversal=0.05)

        assert [p.price for p in pivots] == [100]  # only the initial low confirmed on the way up

    def test_monotonic_series_has_no_confirmed_top(self):
        frame = bars_from_waypoints([100, 110, 120, 130])

        pivots = detect_swings(frame, reversal=0.05)

        assert [p.kind for p in pivots] == [SwingKind.LOW]  # the origin; the running top never confirms

    def test_pivot_indices_are_bar_positions(self):
        frame = bars_from_waypoints([100, 130, 110], bars_per_leg=5)

        pivots = detect_swings(frame, reversal=0.05)

        top = next(p for p in pivots if p.kind is SwingKind.HIGH)
        assert frame["high"].iloc[top.index] == top.price == 130

    def test_alternation_always_holds(self):
        frame = bars_from_waypoints([100, 140, 105, 150, 95, 160, 100, 170])

        pivots = detect_swings(frame, reversal=0.06)

        kinds = [p.kind for p in pivots]
        assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))

    def test_wide_bar_never_yields_same_index_pivots(self):
        # Bar 1 spans >5% on its own: without collapsing, it becomes a swing low
        # AND a swing high at the same index, breaking Wave validation downstream.
        import pandas as pd

        data = {
            "open": [100, 100, 105, 103, 101, 99, 97],
            "high": [100, 112, 105, 103, 101, 99, 97],
            "low": [100, 95, 104, 102, 100, 98, 96],
            "close": [100, 111, 105, 103, 101, 99, 97],
            "volume": [1] * 7,
        }
        frame = pd.DataFrame(data, index=pd.bdate_range("2024-01-01", periods=7))

        pivots = detect_swings(frame, reversal=0.05)

        indices = [p.index for p in pivots]
        assert indices == sorted(set(indices)), "pivot indices must be strictly increasing"
        from little_warren.domain.analysis import segment_waves

        segment_waves(pivots)  # must not raise

    def test_invalid_reversal_rejected(self):
        frame = bars_from_waypoints([100, 110])
        with pytest.raises(ValueError, match="reversal must be > 0"):
            detect_swings(frame, reversal=0)

    def test_missing_columns_rejected(self):
        frame = bars_from_waypoints([100, 110]).drop(columns=["low"])
        with pytest.raises(ValueError, match="missing required columns"):
            detect_swings(frame)
