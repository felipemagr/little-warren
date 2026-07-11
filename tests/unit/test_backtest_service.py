"""Unit tests for the walk-forward backtest (synthetic data)."""

import pytest

from little_warren.application.analysis_service.service import AnalysisService
from little_warren.application.backtest_service.service import BacktestService, TradeOutcome
from tests.fixtures.synthetic import bars_from_waypoints

pytestmark = pytest.mark.unit

IMPULSE = [100, 120, 110, 150, 138, 160]
LEGS = [5, 5, 5, 5, 3]


def backtest(frame):
    service = BacktestService(AnalysisService(provider=None, reversal=0.05), warmup_bars=20)
    return service.run(frame, ticker="TEST")


class TestBacktest:
    def test_short_reaching_wave4_zone_wins(self):
        # Break then decline through the wave-4 target (138).
        frame = bars_from_waypoints(IMPULSE + [130, 125], bars_per_leg=LEGS + [5, 5])

        report = backtest(frame)

        assert len(report.trades) == 1
        trade = report.trades[0]
        assert trade.outcome is TradeOutcome.TARGET
        assert trade.r_multiple is not None and trade.r_multiple > 0
        assert report.hit_rate == 1.0

    def test_short_stopped_out_when_price_reclaims_extreme(self):
        # Break, then a rally through the stop (160 * 1.005) before any target.
        frame = bars_from_waypoints(IMPULSE + [146, 165], bars_per_leg=LEGS + [3, 4])

        report = backtest(frame)

        assert len(report.trades) == 1
        assert report.trades[0].outcome is TradeOutcome.STOP
        assert report.trades[0].r_multiple == -1.0
        assert report.hit_rate == 0.0

    def test_unresolved_trade_stays_open(self):
        # Break confirmed, then the frame ends between stop and target.
        frame = bars_from_waypoints(IMPULSE + [146], bars_per_leg=LEGS + [3])

        report = backtest(frame)

        assert len(report.trades) == 1
        assert report.trades[0].outcome is TradeOutcome.OPEN
        assert report.hit_rate is None

    def test_same_signal_not_traded_twice(self):
        # The same fresh break is visible at several successive as-of bars.
        frame = bars_from_waypoints(IMPULSE + [130, 125], bars_per_leg=LEGS + [5, 5])

        report = backtest(frame)

        assert len(report.trades) == 1

    def test_no_signals_no_trades(self):
        frame = bars_from_waypoints([100, 110, 104, 112, 106, 114], bars_per_leg=5)

        report = backtest(frame)

        assert report.trades == []
