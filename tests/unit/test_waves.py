"""Unit tests for wave segmentation and the Wave value object."""

import pytest
from pydantic import ValidationError

from little_warren.domain.analysis import detect_swings, segment_waves
from little_warren.domain.value_objects.swing import SwingKind, SwingPoint
from little_warren.domain.value_objects.wave import Wave
from tests.fixtures.synthetic import bars_from_waypoints, waves_from_prices

pytestmark = pytest.mark.unit


class TestWave:
    def test_properties(self):
        wave = waves_from_prices([100, 120], bars_per_leg=5)[0]

        assert wave.is_up
        assert wave.price_range == 20
        assert wave.duration == 5
        assert (wave.low, wave.high) == (100, 120)

    def test_retracement_of(self):
        w1, w2 = waves_from_prices([100, 120, 110])

        assert w2.retracement_of(w1) == pytest.approx(0.5)

    def test_end_before_start_rejected(self):
        pivots = waves_from_prices([100, 120])[0]
        with pytest.raises(ValidationError, match="after start index"):
            Wave(start=pivots.end, end=pivots.start)


class TestSegmentWaves:
    def test_pipeline_from_bars_to_waves(self):
        # Trailing drop to 120 confirms the final 160 top: 6 pivots -> 5 waves.
        frame = bars_from_waypoints([100, 120, 110, 150, 138, 160, 120])

        waves = segment_waves(detect_swings(frame, reversal=0.05))

        assert len(waves) == 5
        assert [w.price_range for w in waves] == [20, 10, 40, 12, 22]

    def test_non_alternating_pivots_rejected(self):
        first, second = (
            SwingPoint(index=0, timestamp="2024-01-01T00:00:00", price=100, kind=SwingKind.LOW),
            SwingPoint(index=5, timestamp="2024-01-08T00:00:00", price=90, kind=SwingKind.LOW),
        )
        with pytest.raises(ValueError, match="must alternate"):
            segment_waves([first, second])
