"""Backtest service: walk-forward replay of the analysis pipeline over history.

No look-ahead: the pick at bar t is produced from data up to t only; it is then
resolved forward bar by bar (stop hit vs target hit). Same-bar ambiguity is
resolved conservatively as a stop hit.
"""

from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from little_warren.application.analysis_service.service import AnalysisService
from little_warren.domain.entities import Direction, Pick


class TradeOutcome(StrEnum):
    TARGET = "target"
    STOP = "stop"
    OPEN = "open"


class BacktestTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    pick: Pick
    entry_index: int
    exit_index: int | None
    outcome: TradeOutcome
    r_multiple: float | None
    """Profit in units of initial risk (1.0 = made one risk unit; -1.0 = stopped out)."""


class BacktestReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    bars: int
    trades: list[BacktestTrade]

    @property
    def closed(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.outcome is not TradeOutcome.OPEN]

    @property
    def hit_rate(self) -> float | None:
        closed = self.closed
        if not closed:
            return None
        return sum(1 for t in closed if t.outcome is TradeOutcome.TARGET) / len(closed)

    @property
    def profit_factor(self) -> float | None:
        gains = sum(t.r_multiple for t in self.closed if t.r_multiple and t.r_multiple > 0)
        losses = -sum(t.r_multiple for t in self.closed if t.r_multiple and t.r_multiple < 0)
        if losses == 0:
            return None
        return gains / losses

    @property
    def avg_r(self) -> float | None:
        closed = [t.r_multiple for t in self.closed if t.r_multiple is not None]
        return sum(closed) / len(closed) if closed else None


class BacktestService:
    """Replay the same pipeline the UI uses over history and measure precision."""

    def __init__(self, analysis: AnalysisService, warmup_bars: int = 60):
        self._analysis = analysis
        self._warmup = warmup_bars

    def run(self, frame: pd.DataFrame, ticker: str) -> BacktestReport:
        trades: list[BacktestTrade] = []
        seen: set[tuple] = set()

        for t in range(self._warmup, len(frame)):
            visible = frame.iloc[: t + 1]
            pick = self._analysis.analyze_frame(visible, ticker=ticker, as_of=visible.index[-1].date())
            if pick is None:
                continue
            signature = (pick.direction, round(pick.stop, 6), round(pick.target or 0.0, 6))
            if signature in seen:
                continue
            seen.add(signature)
            trades.append(self._resolve(frame, pick, entry_index=t))

        return BacktestReport(ticker=ticker, bars=len(frame), trades=trades)

    def _resolve(self, frame: pd.DataFrame, pick: Pick, entry_index: int) -> BacktestTrade:
        risk = pick.risk_per_unit
        for i in range(entry_index + 1, len(frame)):
            bar = frame.iloc[i]
            if pick.direction is Direction.SHORT:
                stopped = bar["high"] >= pick.stop
                targeted = pick.target is not None and bar["low"] <= pick.target
            else:
                stopped = bar["low"] <= pick.stop
                targeted = pick.target is not None and bar["high"] >= pick.target
            if stopped:  # conservative: stop wins same-bar ambiguity
                return BacktestTrade(
                    pick=pick, entry_index=entry_index, exit_index=i, outcome=TradeOutcome.STOP, r_multiple=-1.0
                )
            if targeted:
                reward = abs(pick.entry - pick.target)
                return BacktestTrade(
                    pick=pick,
                    entry_index=entry_index,
                    exit_index=i,
                    outcome=TradeOutcome.TARGET,
                    r_multiple=reward / risk if risk > 0 else None,
                )
        return BacktestTrade(
            pick=pick, entry_index=entry_index, exit_index=None, outcome=TradeOutcome.OPEN, r_multiple=None
        )
