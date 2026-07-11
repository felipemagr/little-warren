"""Unit tests for the linea 2-4 trigger mechanism (L24 spec rules)."""

import pytest

from little_warren.domain.analysis import detect_swings, segment_waves
from little_warren.domain.rules.linea_24 import (
    BreakStatus,
    build_linea_24,
    confirms_fifth_failure,
    evaluate_linea_24,
)

pytestmark = pytest.mark.unit

# Up-impulse pivots at 100/120/110/150/138/160; pivots land at bar indices 0,5,10,15,20,23
# (leg durations 5,5,5,5,3), so t5 = 3 bars.
IMPULSE = [100, 120, 110, 150, 138, 160]
LEGS = [5, 5, 5, 5, 3]


def frame_and_waves(extra_waypoints, extra_legs):
    from tests.fixtures.synthetic import bars_from_waypoints

    frame = bars_from_waypoints(IMPULSE + extra_waypoints, bars_per_leg=LEGS + extra_legs)
    pivots = detect_swings(frame, reversal=0.05)
    waves = segment_waves(pivots)[:5]
    return frame, waves


class TestBuildLine:
    def test_line_joins_wave2_and_wave4_ends(self):
        _, waves = frame_and_waves([120], [6])

        line = build_linea_24(waves)

        assert (line.anchor1_index, line.anchor1_price) == (10, 110)
        assert (line.anchor2_index, line.anchor2_price) == (20, 138)
        assert line.slope == pytest.approx(2.8)
        assert line.price_at(25) == pytest.approx(152)

    def test_needs_five_waves(self):
        _, waves = frame_and_waves([120], [6])
        with pytest.raises(ValueError, match="5 impulse waves"):
            build_linea_24(waves[:4])


class TestEvaluate:
    def test_fast_break_confirms(self):
        # Sharp reversal 160 -> 130 in 5 bars pierces the rising line immediately.
        frame, waves = frame_and_waves([130], [5])

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.status is BreakStatus.CONFIRMED
        assert outcome.tr is not None and outcome.tr <= outcome.t5
        assert "L24-03" in outcome.rules_applied

    def test_slow_drift_is_slow(self):
        # Shallow drift 160 -> 150 over 10 bars: the line catches up only after t5.
        frame, waves = frame_and_waves([150], [10])

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.status is BreakStatus.SLOW
        assert outcome.tr is not None and outcome.tr > outcome.t5
        assert "L24-05" in outcome.rules_applied

    def test_no_data_after_wave5_is_pending(self):
        # Post-pattern dip to 155 confirms the 160 top (3% threshold) but stays
        # above the rising line, and the frame ends there: no break yet.
        from tests.fixtures.synthetic import bars_from_waypoints

        frame = bars_from_waypoints(IMPULSE + [155], bars_per_leg=LEGS + [2])
        waves = segment_waves(detect_swings(frame, reversal=0.03))[:5]

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.status is BreakStatus.PENDING

    def test_wave3_piercing_line_invalidates(self):
        frame, waves = frame_and_waves([130], [5])
        frame.iloc[12, frame.columns.get_loc("low")] = 100.0  # dip below the line during wave 3

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.status is BreakStatus.INVALID_LINE
        assert "L24-02" in outcome.rules_applied


class TestViolenceAndFifthFailure:
    def test_sharp_break_is_violent(self):
        # Break leg travels 25/bar vs wave-5 pace of ~7.3/bar.
        frame, waves = frame_and_waves([110], [2])

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.status is BreakStatus.CONFIRMED
        assert outcome.violent

    def test_gentle_break_is_not_violent(self):
        # Break leg travels 6/bar, below 1.5x the wave-5 pace.
        frame, waves = frame_and_waves([130], [5])

        outcome = evaluate_linea_24(frame, waves)

        assert not outcome.violent

    def test_fifth_failure_confirmed_when_wave5_never_exceeded_wave3(self):
        # Wave 5 tops at 146 < wave-3 end 152, then a violent collapse.
        from tests.fixtures.synthetic import bars_from_waypoints

        frame = bars_from_waypoints([100, 120, 110, 152, 136, 146, 100], bars_per_leg=[5, 5, 5, 5, 3, 2])
        waves = segment_waves(detect_swings(frame, reversal=0.05))[:5]

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.violent
        assert confirms_fifth_failure(waves, outcome)

    def test_normal_impulse_is_not_fifth_failure(self):
        frame, waves = frame_and_waves([110], [2])  # violent break but wave 5 exceeded wave 3

        outcome = evaluate_linea_24(frame, waves)

        assert outcome.violent
        assert not confirms_fifth_failure(waves, outcome)
