"""Grid calibration of the ASSUMED parameters via walk-forward backtest on the DEV universe.

Sweeps swing reversal x stop offset x entry mode on DEV tickers only (HOLDOUT stays
untouched until a winner is chosen), then reports per-combo metrics and evidence-bucket
hit rates for re-deriving the confidence weights.

Usage:
    uv run python scripts/calibrate.py
    uv run python scripts/calibrate.py --holdout --reversal 0.05 --stop 0.005 --entry line-level
"""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from universe_backtest import DEV_UNIVERSE, HOLDOUT_UNIVERSE

REVERSALS = (0.04, 0.05, 0.06, 0.08)
STOP_OFFSETS = (0.005, 0.01, 0.02)
ENTRY_MODES = ("break-close", "line-level")
BASELINE = (0.05, 0.005, "break-close")
MIN_CLOSED_TRADES = 60
LOOKBACK_DAYS = 2500
END_DATE = date.today()
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("^", "idx_").replace(".", "_")
    return CACHE_DIR / f"ohlcv_{safe}_{END_DATE}.pkl"


def load_frame(ticker: str) -> pd.DataFrame:
    """OHLCV frame for `ticker`, cached to data/cache/ so the grid never re-downloads."""
    path = _cache_path(ticker)
    if path.exists():
        return pd.read_pickle(path)
    from little_warren.infrastructure.data import YFinanceProvider

    frame = YFinanceProvider().fetch_ohlcv(ticker, start=END_DATE - timedelta(days=LOOKBACK_DAYS), end=END_DATE)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(path)
    return frame


def prefetch(tickers: tuple[str, ...]) -> list[str]:
    """Populate the frame cache once, serially; drop tickers that fail to download."""
    available = []
    for ticker in tickers:
        try:
            load_frame(ticker)
            available.append(ticker)
        except Exception as error:  # noqa: BLE001 - sweep must survive bad tickers
            print(f"{ticker}: prefetch ERROR {error}")
    return available


def run_cell(ticker: str, reversal: float, stop_offset: float, entry_mode: str) -> list[dict]:
    """One (ticker, combo) walk-forward backtest; returns per-trade records with evidence."""
    from little_warren.application.analysis_service.service import AnalysisService
    from little_warren.application.backtest_service.service import BacktestService

    try:
        frame = load_frame(ticker)
        analysis = AnalysisService(provider=None, reversal=reversal, stop_offset=stop_offset, entry_mode=entry_mode)
        report = BacktestService(analysis).run(frame, ticker=ticker)
    except Exception as error:  # noqa: BLE001 - sweep must survive bad tickers
        print(f"{ticker} r={reversal} s={stop_offset} {entry_mode}: ERROR {error}")
        return []
    return [
        {
            "ticker": ticker,
            "as_of": str(t.pick.as_of),
            "direction": t.pick.direction.value,
            "confidence": t.pick.confidence,
            "outcome": t.outcome.value,
            "r": t.r_multiple,
            "evidence": t.pick.evidence,
        }
        for t in report.trades
    ]


def summarize(trades: list[dict]) -> dict:
    closed = [t for t in trades if t["outcome"] != "open"]
    wins = sum(1 for t in closed if t["outcome"] == "target")
    gains = sum(t["r"] for t in closed if t["r"] and t["r"] > 0)
    losses = -sum(t["r"] for t in closed if t["r"] and t["r"] < 0)
    return {
        "trades": len(trades),
        "closed": len(closed),
        "hit_rate": wins / len(closed) if closed else None,
        "profit_factor": gains / losses if losses else None,
        "avg_r": sum(t["r"] for t in closed) / len(closed) if closed else None,
    }


def run_combos(tickers: list[str], combos: list[tuple[float, float, str]]) -> dict[tuple, list[dict]]:
    """Run every (combo, ticker) cell in a process pool; frames come from the local cache."""
    results: dict[tuple, list[dict]] = {combo: [] for combo in combos}
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(run_cell, ticker, reversal, stop, entry): (reversal, stop, entry)
            for (reversal, stop, entry) in combos
            for ticker in tickers
        }
        for done, future in enumerate(as_completed(futures), start=1):
            results[futures[future]].extend(future.result())
            if done % 50 == 0:
                print(f"... {done}/{len(futures)} cells done")
    return results


def _fmt(value: float | None, spec: str) -> str:
    return format(value, spec) if value is not None else "n/a"


def print_grid(results: dict[tuple, list[dict]]) -> list[dict]:
    records = []
    for (reversal, stop, entry), trades in results.items():
        summary = summarize(trades)
        records.append({"reversal": reversal, "stop_offset": stop, "entry_mode": entry, **summary})
    records.sort(key=lambda r: (r["profit_factor"] is not None, r["profit_factor"] or 0), reverse=True)

    print("\n===== DEV GRID (sorted by profit factor) =====")
    print(f"{'reversal':>8} {'stop':>6} {'entry':<12} {'closed':>6} {'hit%':>6} {'PF':>6} {'avgR':>6}")
    for r in records:
        flag = " *" if r["closed"] >= MIN_CLOSED_TRADES else ""
        print(
            f"{r['reversal']:>8} {r['stop_offset']:>6} {r['entry_mode']:<12} {r['closed']:>6} "
            f"{_fmt(r['hit_rate'] and 100 * r['hit_rate'], '6.1f')} "
            f"{_fmt(r['profit_factor'], '6.2f')} {_fmt(r['avg_r'], '+6.2f')}{flag}"
        )
    print(f"(* = eligible: >= {MIN_CLOSED_TRADES} closed trades)")
    return records


def print_evidence_buckets(label: str, trades: list[dict]) -> None:
    """Empirical hit rate per evidence bucket, for re-deriving confidence weights."""
    closed = [t for t in trades if t["outcome"] != "open"]
    print(f"\n----- evidence buckets: {label} ({len(closed)} closed) -----")

    def show(name: str, subset: list[dict]) -> None:
        if not subset:
            print(f"  {name:<26} 0 trades")
            return
        wins = sum(1 for t in subset if t["outcome"] == "target")
        avg_r = sum(t["r"] for t in subset) / len(subset)
        print(f"  {name:<26} {len(subset):>4} trades  {100 * wins / len(subset):5.1f}% hit  avg R {avg_r:+.2f}")

    for flag in ("violent", "fifth_failure", "terminal"):
        for value in (True, False):
            show(f"{flag}={value}", [t for t in closed if bool(t["evidence"].get(flag)) is value])
    for wave in (1, 3, 5, None):
        show(f"extended_wave={wave}", [t for t in closed if t["evidence"].get("extended_wave") == wave])

    profiles: dict[tuple, list[dict]] = {}
    for t in closed:
        e = t["evidence"]
        key = (bool(e.get("violent")), bool(e.get("fifth_failure")), bool(e.get("terminal")))
        profiles.setdefault(key, []).append(t)
    for (violent, fifth, terminal), subset in sorted(profiles.items()):
        show(f"v={int(violent)} f5={int(fifth)} ter={int(terminal)}", subset)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", action="store_true", help="run one combo on the HOLDOUT universe")
    parser.add_argument("--reversal", type=float, default=BASELINE[0])
    parser.add_argument("--stop", type=float, default=BASELINE[1])
    parser.add_argument("--entry", choices=ENTRY_MODES, default=BASELINE[2])
    args = parser.parse_args()

    if args.holdout:
        tickers = prefetch(HOLDOUT_UNIVERSE)
        combo = (args.reversal, args.stop, args.entry)
        trades = run_combos(tickers, [combo])[combo]
        summary = summarize(trades)
        print(f"\n===== HOLDOUT ({len(tickers)} tickers) reversal={combo[0]} stop={combo[1]} entry={combo[2]} =====")
        print(
            f"closed: {summary['closed']}  hit: {_fmt(summary['hit_rate'] and 100 * summary['hit_rate'], '.1f')}%  "
            f"PF: {_fmt(summary['profit_factor'], '.2f')}  avg R: {_fmt(summary['avg_r'], '+.2f')}"
        )
        print_evidence_buckets("holdout combo", trades)
        out = CACHE_DIR / "calibration_holdout.json"
        out.write_text(json.dumps({"combo": combo, "summary": summary, "trades": trades}, indent=1))
        print(f"detail: {out}")
        return

    tickers = prefetch(DEV_UNIVERSE)
    print(f"DEV universe: {len(tickers)}/{len(DEV_UNIVERSE)} tickers available")
    combos = [(r, s, e) for r in REVERSALS for s in STOP_OFFSETS for e in ENTRY_MODES]
    results = run_combos(tickers, combos)
    records = print_grid(results)

    eligible = [r for r in records if r["closed"] >= MIN_CLOSED_TRADES and r["profit_factor"] is not None]
    if eligible:
        best = max(eligible, key=lambda r: r["profit_factor"])
        best_combo = (best["reversal"], best["stop_offset"], best["entry_mode"])
        reversal, stop, entry = best_combo
        print(f"\nBEST (PF, >= {MIN_CLOSED_TRADES} closed): reversal={reversal} stop={stop} entry={entry}")
        print_evidence_buckets("baseline " + str(BASELINE), results[BASELINE])
        print_evidence_buckets("best " + str(best_combo), results[best_combo])

    out = CACHE_DIR / "calibration_dev.json"
    payload = [
        {"combo": list(combo), "summary": summarize(trades), "trades": trades} for combo, trades in results.items()
    ]
    out.write_text(json.dumps(payload, indent=1))
    print(f"\ndetail: {out}")


if __name__ == "__main__":
    main()
