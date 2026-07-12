"""Unit tests for momentum indicators."""

import pytest

from little_warren.domain.analysis.indicators import stochastic_k, stochastic_k_at, weekly_stochastic_k_at
from tests.fixtures.synthetic import bars_from_waypoints

pytestmark = pytest.mark.unit


class TestStochastic:
    def test_close_at_top_of_range_reads_100(self):
        frame = bars_from_waypoints([100, 130], bars_per_leg=25)

        assert stochastic_k(frame).iloc[-1] == pytest.approx(100.0)

    def test_close_at_bottom_of_range_reads_0(self):
        frame = bars_from_waypoints([130, 100], bars_per_leg=25)

        assert stochastic_k(frame).iloc[-1] == pytest.approx(0.0)

    def test_midrange_reads_50(self):
        # Every bar spans 100-120 with the close pinned at 110 = exact midrange.
        import pandas as pd

        index = pd.bdate_range("2024-01-01", periods=20)
        frame = pd.DataFrame({"open": 110.0, "high": 120.0, "low": 100.0, "close": 110.0, "volume": 1}, index=index)

        value = stochastic_k_at(frame, len(frame) - 1)

        assert value == pytest.approx(50.0)

    def test_no_look_ahead(self):
        rising_then_crash = bars_from_waypoints([100, 130, 90], bars_per_leg=25)

        at_top = stochastic_k_at(rising_then_crash, 25)

        assert at_top == pytest.approx(100.0)  # the crash after bar 25 must not leak in

    def test_weekly_needs_enough_history(self):
        short_frame = bars_from_waypoints([100, 120], bars_per_leg=30)

        assert weekly_stochastic_k_at(short_frame, 29) is None

    def test_weekly_with_long_history(self):
        frame = bars_from_waypoints([100, 150], bars_per_leg=120)

        value = weekly_stochastic_k_at(frame, 119)

        assert value == pytest.approx(100.0)
