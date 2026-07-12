"""Unit tests for the analysis service pipeline (synthetic data, no network)."""

from datetime import date

import pytest

from little_warren.application.analysis_service.service import AnalysisService
from little_warren.domain.entities import Direction
from tests.fixtures.synthetic import bars_from_waypoints

pytestmark = pytest.mark.unit

AS_OF = date(2024, 6, 1)


def service() -> AnalysisService:
    return AnalysisService(provider=None, reversal=0.05)  # analyze_frame only; no fetching


class TestAnalyzeFrame:
    def test_confirmed_break_produces_short_pick(self):
        # Up-impulse 100..160 then sharp reversal: trade against the concluded impulse.
        frame = bars_from_waypoints([100, 120, 110, 150, 138, 160, 130], bars_per_leg=[5, 5, 5, 5, 3, 5])

        pick = service().analyze_frame(frame, ticker="TEST", as_of=AS_OF)

        assert pick is not None
        assert pick.direction is Direction.SHORT
        assert pick.stop == pytest.approx(160 * 1.02)  # STP-02 beyond the wave-5 extreme (calibrated offset)
        assert pick.entry == pytest.approx(152.0)  # LINE_LEVEL entry at the 2-4 line on the break bar
        assert pick.target == pytest.approx(138)  # x3 impulse -> wave-4 zone
        assert pick.confidence == pytest.approx(0.70)  # plain confirmed break, empirically the best bucket
        assert "L24-03" in pick.rules_fired and "STP-02" in pick.rules_fired

    def test_down_impulse_produces_long_pick(self):
        prices = [round(200 - (p - 100), 4) for p in [100, 120, 110, 150, 138, 160, 130]]
        frame = bars_from_waypoints(prices, bars_per_leg=[5, 5, 5, 5, 3, 5])

        pick = service().analyze_frame(frame, ticker="TEST", as_of=AS_OF)

        assert pick is not None
        assert pick.direction is Direction.LONG
        assert pick.stop == pytest.approx(140 * 0.98)  # wave-5 extreme of the mirrored impulse
        assert pick.stop < pick.entry

    def test_fifth_failure_targets_pattern_origin_with_higher_confidence(self):
        frame = bars_from_waypoints([100, 120, 110, 152, 136, 146, 100], bars_per_leg=[5, 5, 5, 5, 3, 2])

        pick = service().analyze_frame(frame, ticker="TEST", as_of=AS_OF)

        assert pick is not None
        assert pick.target == pytest.approx(100)  # full retrace to origin
        assert "L24-09" in pick.rules_fired
        # Empirical weights: fifth failures underperform plain breaks (0.70 - 0.15).
        assert pick.confidence == pytest.approx(0.55)
        assert pick.evidence["fifth_failure"] is True

    def test_no_pick_when_no_impulse(self):
        frame = bars_from_waypoints([100, 110, 104, 112, 106, 114, 108], bars_per_leg=5)

        assert service().analyze_frame(frame, ticker="TEST", as_of=AS_OF) is None

    def test_no_pick_when_break_is_stale(self):
        # Confirmed break followed by 30 bars of drift: too old to act on.
        frame = bars_from_waypoints([100, 120, 110, 150, 138, 160, 130, 128], bars_per_leg=[5, 5, 5, 5, 3, 5, 30])

        assert service().analyze_frame(frame, ticker="TEST", as_of=AS_OF) is None

    def test_pick_is_traceable(self):
        frame = bars_from_waypoints([100, 120, 110, 150, 138, 160, 130], bars_per_leg=[5, 5, 5, 5, 3, 5])

        pick = service().analyze_frame(frame, ticker="TEST", as_of=AS_OF)

        assert pick.rules_fired[0] == "FND-10"
        assert len(pick.rules_fired) == len(set(pick.rules_fired))
