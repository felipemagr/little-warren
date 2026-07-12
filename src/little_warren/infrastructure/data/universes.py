"""Ticker universes for the scanner: static presets plus full index constituents.

Index members are fetched from Wikipedia, normalized to Yahoo symbols and cached
on disk for a week; on any failure the loader falls back to the static seed so
the scanner keeps working offline.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from loguru import logger

CACHE_DIR = Path("data/cache/universes")
CACHE_TTL_SECONDS = 7 * 24 * 3600

US_LARGE_CAPS = (  # noqa: SIM905 - space-joined blocks stay readable for 100+ tickers
    "AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO JPM V MA UNH HD PG KO PEP MRK ABBV XOM CVX "
    "WMT COST NFLX AMD INTC CRM ORCL ADBE CSCO QCOM TXN IBM BA CAT GE MMM NKE MCD SBUX DIS "
    "LLY JNJ PFE BMY AMGN GILD GS MS BAC C WFC BLK SCHW AXP T VZ TMUS CMCSA "
    "LOW TJX TGT ORLY YUM CMG MAR DAL UNP CSX FDX UPS DE HON LMT RTX F GM "
    "NEE DUK SO SLB COP EOG MPC VLO FCX NEM NUE LIN ECL SHW KMB CL GIS HSY MO PM STZ "
    "ANET PANW FTNT CRWD SNOW MDB NOW INTU ADP MU LRCX AMAT KLAC ADI NXPI SNPS CDNS "
    "PYPL COIN ABNB UBER SHOP EBAY"
).split()

IBEX35 = (  # noqa: SIM905
    "ACS.MC ACX.MC AENA.MC AMS.MC ANA.MC ANE.MC BBVA.MC BKT.MC CABK.MC CLNX.MC COL.MC "
    "ELE.MC ENG.MC FDR.MC FER.MC GRF.MC IAG.MC IBE.MC IDR.MC ITX.MC LOG.MC MAP.MC MEL.MC "
    "MRL.MC MTS.MC NTGY.MC RED.MC REP.MC ROVI.MC SAB.MC SAN.MC SCYR.MC SLR.MC TEF.MC UNI.MC"
).split()

EUROPE_CORE = (  # noqa: SIM905
    "AIR.PA MC.PA OR.PA SAN.PA TTE.PA BNP.PA SAP.DE SIE.DE ALV.DE BAS.DE BMW.DE DTE.DE "
    "ASML.AS PHIA.AS INGA.AS AD.AS NESN.SW NOVN.SW UBSG.SW AZN.L SHEL.L HSBA.L BP.L GSK.L ULVR.L RIO.L"
).split()

INDICES = "^GSPC ^IXIC ^DJI ^RUT ^IBEX ^STOXX50E ^GDAXI ^FCHI ^FTSE".split()  # noqa: SIM905

# name -> (wikipedia url, symbol column, yahoo suffix)
WIKIPEDIA_SOURCES: dict[str, tuple[str, str, str]] = {
    "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", ""),
    "dax40": ("https://en.wikipedia.org/wiki/DAX", "Ticker", ".DE"),
    "ftse100": ("https://en.wikipedia.org/wiki/FTSE_100_Index", "Ticker", ".L"),
}


def normalize_symbols(symbols: list[str], suffix: str) -> list[str]:
    """Turn raw index symbols into Yahoo Finance tickers."""
    normalized = []
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        normalized.append(_to_yahoo(symbol, suffix))
    return list(dict.fromkeys(normalized))


KNOWN_EXCHANGE_SUFFIXES = {"L", "PA", "DE", "AS", "SW", "MC", "MI", "BR", "VI", "ST", "CO", "HE"}


def _to_yahoo(symbol: str, suffix: str) -> str:
    """US tickers: BRK.B -> BRK-B. Suffixed markets keep an existing exchange suffix
    (a DAX row can list AIR.PA for Airbus); share-class dots become dashes before the
    suffix is appended (LSE BT.A -> BT-A.L, AV. -> AV.L)."""
    if not suffix:
        return symbol.replace(".", "-")
    head, _, tail = symbol.rstrip(".").rpartition(".")
    if head and tail in KNOWN_EXCHANGE_SUFFIXES:
        return symbol
    return symbol.rstrip(".").replace(".", "-") + suffix.upper()


def _fetch_from_wikipedia(url: str, column: str) -> list[str]:
    from io import StringIO

    import requests

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (little-warren scanner)"}, timeout=30)
    response.raise_for_status()
    for table in pd.read_html(StringIO(response.text)):
        if column in table.columns:
            return [str(value) for value in table[column].dropna()]
    raise ValueError(f"no table with column {column!r} at {url}")


def load_index(
    name: str,
    cache_dir: Path = CACHE_DIR,
    fetcher: Callable[[str, str], list[str]] | None = None,
) -> list[str]:
    """Constituents of a named index, disk-cached; empty list when unavailable."""
    url, column, suffix = WIKIPEDIA_SOURCES[name]
    cache_file = cache_dir / f"{name}.json"
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_TTL_SECONDS:
        return json.loads(cache_file.read_text())
    try:
        symbols = normalize_symbols((fetcher or _fetch_from_wikipedia)(url, column), suffix)
    except Exception as error:  # noqa: BLE001 - offline or layout change must not break the scanner
        logger.warning("could not load {} constituents: {}", name, error)
        return json.loads(cache_file.read_text()) if cache_file.exists() else []
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(symbols))
    return symbols


def get_presets() -> dict[str, list[str]]:
    """All scanner presets; dynamic indices appear only when resolvable."""
    presets: dict[str, list[str]] = {}
    for label, name, fallback in (
        ("S&P 500", "sp500", US_LARGE_CAPS),
        ("DAX 40", "dax40", []),
        ("FTSE 100", "ftse100", []),
    ):
        constituents = load_index(name) or fallback
        if constituents:
            presets[label] = constituents
    presets["IBEX 35"] = IBEX35
    presets["Europe core"] = EUROPE_CORE
    presets["Indices"] = INDICES
    return presets


PRESETS: dict[str, list[str]] = {
    "US large caps": US_LARGE_CAPS,
    "Spain": IBEX35,
    "Europe": EUROPE_CORE,
    "Indices": INDICES,
}
