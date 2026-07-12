"""Large-scale validation: ~200 tickers x 10 years, honest fills, round-trip costs.

Parameters are FROZEN (calibrated defaults); nothing here is tuned. The headline
cohort is OUT-OF-SAMPLE: every ticker not in the 30-ticker dev split the
parameters were calibrated on. Usage: uv run python scripts/big_validation.py
"""

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta

from universe_backtest import DEV_UNIVERSE
from universe_backtest import UNIVERSE as CORE_UNIVERSE

ROUND_TRIP_COST = 0.0015
"""Round-trip commissions + spread + slippage as a fraction of entry notional."""

EXTRA_UNIVERSE = (  # noqa: SIM905 - a space-joined block is far more readable for 200+ tickers
    # S&P large/mid caps beyond the core 50
    "LLY JNJ PFE BMY AMGN GILD CVS CI HUM MDT ISRG SYK BSX ZTS TMO DHR ABT "
    "GS MS BAC C WFC BLK SCHW AXP COF USB PNC TFC BK "
    "T VZ TMUS CMCSA CHTR PARA WBD FOX EA TTWO "
    "LOW TJX ROST DG DLTR TGT BBY ORLY AZO YUM CMG DPZ MAR HLT RCL CCL DAL UAL AAL LUV "
    "UNP CSX NSC FDX UPS DE CMI ETN EMR HON LMT RTX NOC GD TXT "
    "F GM HOG BWA APTV "
    "MMC AON AJG TRV ALL PGR CB MET PRU AFL "
    "SPG PLD AMT CCI EQIX PSA O AVB EQR "
    "NEE DUK SO D AEP EXC SRE XEL ED PEG "
    "SLB HAL BKR OXY COP EOG PXD MPC VLO PSX KMI WMB "
    "FCX NEM NUE STLD DD DOW LYB APD LIN ECL SHW PPG "
    "KMB CL CHD CLX GIS K KHC HSY MKC SJM CAG CPB TSN HRL "
    "MO PM STZ TAP KDP MNST "
    "ANET PANW FTNT CRWD ZS NET DDOG SNOW MDB TEAM WDAY NOW INTU ADP PAYX "
    "MU LRCX AMAT KLAC ADI MCHP NXPI ON SWKS TER SNPS CDNS "
    "PYPL SQ COIN HOOD SOFI "
    "ABNB UBER LYFT DASH ETSY EBAY SHOP "
    # Europe
    "TEF.MC ELE.MC CABK.MC FER.MC ACS.MC AMS.MC GRF.MC ENG.MC "
    "AIR.PA MC.PA OR.PA SAN.PA TTE.PA BNP.PA "
    "SAP.DE SIE.DE ALV.DE BAS.DE BAYN.DE BMW.DE MBG.DE DTE.DE "
    "ASML.AS PHIA.AS INGA.AS AD.AS "
    "NESN.SW NOVN.SW ROG.SW UBSG.SW "
    "AZN.L SHEL.L HSBA.L BP.L GSK.L ULVR.L RIO.L "
    # Indices
    "^STOXX50E ^GDAXI ^FCHI ^FTSE ^RUT"
).split()

UNIVERSE = sorted(set(CORE_UNIVERSE) | set(EXTRA_UNIVERSE))
LOOKBACK_DAYS = 3650


def run_ticker(ticker: str) -> list[dict]:
    from little_warren.application.analysis_service.service import AnalysisService
    from little_warren.application.backtest_service.service import BacktestService
    from little_warren.infrastructure.data import YFinanceProvider

    end = date.today()
    try:
        frame = YFinanceProvider().fetch_ohlcv(ticker, start=end - timedelta(days=LOOKBACK_DAYS), end=end)
        report = BacktestService(AnalysisService(provider=None)).run(frame, ticker=ticker)
    except Exception as error:  # noqa: BLE001 - validation must survive bad tickers
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
            "entry": t.pick.entry,
            "stop": t.pick.stop,
            "rules": t.pick.rules_fired,
        }
        for t in report.trades
    ]


def cost_adjusted_r(trade: dict) -> float | None:
    """Subtract round-trip costs, expressed in R (risk units)."""
    if trade["r"] is None:
        return None
    risk = abs(trade["entry"] - trade["stop"])
    if risk == 0:
        return trade["r"]
    return trade["r"] - (ROUND_TRIP_COST * trade["entry"]) / risk


def summarize(label: str, cohort: list[dict]) -> None:
    closed = [t for t in cohort if t["outcome"] != "open"]
    if not closed:
        print(f"{label}: no closed trades")
        return
    adjusted = [cost_adjusted_r(t) for t in closed]
    wins = sum(1 for t in closed if t["outcome"] == "target")
    gains = sum(r for r in adjusted if r and r > 0)
    losses = -sum(r for r in adjusted if r and r < 0)
    pf = f"{gains / losses:.2f}" if losses else "inf"
    avg = sum(r for r in adjusted if r is not None) / len(closed)
    print(f"{label}: {len(closed)} closed | hit {100 * wins / len(closed):.1f}% | PF {pf} | avg {avg:+.2f}R (net of costs)")
    for name, bucket in (
        ("HIGH-CONF (>=0.70)", [t for t in closed if t["confidence"] >= 0.70]),
        ("low-conf  (<0.70)", [t for t in closed if t["confidence"] < 0.70]),
    ):
        if bucket:
            bucket_wins = sum(1 for t in bucket if t["outcome"] == "target")
            bucket_adj = [cost_adjusted_r(t) for t in bucket]
            bucket_avg = sum(r for r in bucket_adj if r is not None) / len(bucket)
            print(
                f"  {name}: {len(bucket)} trades | precision {100 * bucket_wins / len(bucket):.1f}% "
                f"| avg {bucket_avg:+.2f}R"
            )


def main() -> None:
    trades: list[dict] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(run_ticker, t): t for t in UNIVERSE}
        for future in as_completed(futures):
            trades.extend(future.result())
            completed += 1
            if completed % 25 == 0:
                print(f"...{completed}/{len(UNIVERSE)} tickers done")

    print(f"\n===== BIG VALIDATION (frozen params, honest fills, {ROUND_TRIP_COST:.2%} costs) =====")
    oos = [t for t in trades if t["ticker"] not in DEV_UNIVERSE]
    summarize("OUT-OF-SAMPLE", oos)
    summarize("ALL          ", trades)

    print("\n--- high-confidence precision by year (out-of-sample) ---")
    high = [t for t in oos if t["confidence"] >= 0.70 and t["outcome"] != "open"]
    for year in sorted({t["as_of"][:4] for t in high}):
        year_trades = [t for t in high if t["as_of"].startswith(year)]
        year_wins = sum(1 for t in year_trades if t["outcome"] == "target")
        print(f"  {year}: {len(year_trades):3d} trades | precision {100 * year_wins / len(year_trades):.1f}%")

    with open("data/cache/big_validation.json", "w") as handle:
        json.dump(trades, handle, indent=1)
    print("detail: data/cache/big_validation.json")


if __name__ == "__main__":
    main()
