"""Universe-wide walk-forward QA backtest. Usage: uv run python scripts/universe_backtest.py"""

import json
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta

UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "AVGO",
    "JPM",
    "V",
    "MA",
    "UNH",
    "HD",
    "PG",
    "KO",
    "PEP",
    "MRK",
    "ABBV",
    "XOM",
    "CVX",
    "WMT",
    "COST",
    "NFLX",
    "AMD",
    "INTC",
    "CRM",
    "ORCL",
    "ADBE",
    "CSCO",
    "QCOM",
    "TXN",
    "IBM",
    "BA",
    "CAT",
    "GE",
    "MMM",
    "NKE",
    "MCD",
    "SBUX",
    "DIS",
    "SAN.MC",
    "BBVA.MC",
    "ITX.MC",
    "IBE.MC",
    "REP.MC",
    "TEF.MC",
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^IBEX",
]

# Deterministic DEV/HOLDOUT split
_SPLIT_SEED = 42
_DEV_SIZE = 30
_shuffled = sorted(UNIVERSE)
random.Random(_SPLIT_SEED).shuffle(_shuffled)
DEV_UNIVERSE = tuple(sorted(_shuffled[:_DEV_SIZE]))
HOLDOUT_UNIVERSE = tuple(sorted(_shuffled[_DEV_SIZE:]))


def run_ticker(ticker: str) -> list[dict]:
    from little_warren.application.analysis_service.service import AnalysisService
    from little_warren.application.backtest_service.service import BacktestService
    from little_warren.infrastructure.data import YFinanceProvider

    end = date.today()
    try:
        frame = YFinanceProvider().fetch_ohlcv(ticker, start=end - timedelta(days=2500), end=end)
        report = BacktestService(AnalysisService(provider=None)).run(frame, ticker=ticker)
    except Exception as error:  # noqa: BLE001 - QA sweep must survive bad tickers
        print(f"{ticker}: ERROR {error}")
        return []
    return [
        {
            "ticker": ticker,
            "as_of": str(t.pick.as_of),
            "direction": t.pick.direction.value,
            "confidence": t.pick.confidence,
            "outcome": t.outcome.value,
            "r": t.r_multiple,
            "rules": t.pick.rules_fired,
        }
        for t in report.trades
    ]


def main() -> None:
    trades: list[dict] = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(run_ticker, t): t for t in UNIVERSE}
        for future in as_completed(futures):
            result = future.result()
            trades.extend(result)
            print(f"{futures[future]}: {len(result)} trades")

    def summarize(label: str, cohort: list[dict]) -> None:
        closed = [t for t in cohort if t["outcome"] != "open"]
        if not closed:
            print(f"{label}: no closed trades")
            return
        wins = [t for t in closed if t["outcome"] == "target"]
        gains = sum(t["r"] for t in closed if t["r"] and t["r"] > 0)
        losses = -sum(t["r"] for t in closed if t["r"] and t["r"] < 0)
        pf = f"{gains / losses:.2f}" if losses else "inf"
        avg = sum(t["r"] for t in closed if t["r"] is not None) / len(closed)
        print(f"{label}: {len(closed)} closed | hit {100 * len(wins) / len(closed):.1f}% | PF {pf} | avg {avg:+.2f}R")
        high = [t for t in closed if t["confidence"] >= 0.70]
        if high:
            high_wins = sum(1 for t in high if t["outcome"] == "target")
            print(f"  HIGH-CONFIDENCE (>=0.70): {len(high)} trades | precision {100 * high_wins / len(high):.1f}%")
        low = [t for t in closed if t["confidence"] < 0.70]
        if low:
            low_wins = sum(1 for t in low if t["outcome"] == "target")
            print(f"  low-confidence  (<0.70): {len(low)} trades | precision {100 * low_wins / len(low):.1f}%")

    print("\n===== AGGREGATE (calibrated defaults) =====")
    dev = [t for t in trades if t["ticker"] in DEV_UNIVERSE]
    holdout = [t for t in trades if t["ticker"] in HOLDOUT_UNIVERSE]
    summarize("DEV     ", dev)
    summarize("HOLDOUT ", holdout)
    summarize("ALL     ", trades)
    with open("data/cache/universe_backtest.json", "w") as handle:
        json.dump(trades, handle, indent=1)
    print("detail: data/cache/universe_backtest.json")


if __name__ == "__main__":
    main()
