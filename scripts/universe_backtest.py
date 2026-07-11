"""Universe-wide walk-forward QA backtest. Usage: uv run python scripts/universe_backtest.py"""

import json
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


def run_ticker(ticker: str) -> list[dict]:
    from little_warren.application.analysis_service.service import AnalysisService
    from little_warren.application.backtest_service.service import BacktestService
    from little_warren.infrastructure.data import YFinanceProvider

    end = date.today()
    try:
        frame = YFinanceProvider().fetch_ohlcv(ticker, start=end - timedelta(days=2500), end=end)
        report = BacktestService(AnalysisService(provider=None, reversal=0.05)).run(frame, ticker=ticker)
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

    closed = [t for t in trades if t["outcome"] != "open"]
    wins = [t for t in closed if t["outcome"] == "target"]
    gains = sum(t["r"] for t in closed if t["r"] and t["r"] > 0)
    losses = -sum(t["r"] for t in closed if t["r"] and t["r"] < 0)

    print("\n===== AGGREGATE =====")
    print(f"tickers: {len(UNIVERSE)}  trades: {len(trades)}  closed: {len(closed)}")
    if closed:
        print(f"HIT RATE: {100 * len(wins) / len(closed):.1f}%")
        print(f"profit factor: {gains / losses:.2f}" if losses else "profit factor: inf")
        print(f"avg R: {sum(t['r'] for t in closed if t['r'] is not None) / len(closed):+.2f}")
        for lo, hi in ((0.0, 0.55), (0.55, 0.7), (0.7, 1.0)):
            bucket = [t for t in closed if lo <= t["confidence"] < hi]
            if bucket:
                rate = 100 * sum(1 for t in bucket if t["outcome"] == "target") / len(bucket)
                print(f"confidence [{lo:.2f}-{hi:.2f}): {len(bucket)} trades, {rate:.1f}% hit")
    with open("data/cache/universe_backtest.json", "w") as handle:
        json.dump(trades, handle, indent=1)
    print("detail: data/cache/universe_backtest.json")


if __name__ == "__main__":
    main()
