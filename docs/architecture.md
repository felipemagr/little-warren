# Architecture

little-warren follows a 3-layer clean architecture.
Dependencies point inward only: `infrastructure -> application -> domain`; `config` is a leaf.

## Data flow

```
market data (yfinance)                          [infrastructure/data]
        |
        v
OHLCV frame (open/high/low/close/volume)
        |
        v
swing detection -> wave & pattern classification [domain/rules  <- codifies the local spec]
        |
        v
signal aggregation -> confidence scoring         [application/analysis_service]
        |
        v
Pick(ticker, direction, entry, stop, target, confidence, rules_fired)
        |
        +--> CLI / Streamlit UI                  [infrastructure/cli, infrastructure/ui]
        +--> backtest replay -> precision metrics [application/backtest_service + eval/]
```

## Layers

- **domain/** — pure logic. `entities/` (Pick, Signal), `value_objects/` (swings, waves, pattern matches), `rules/` (one module per pattern family; every function tagged with its spec rule ID).
- **application/** — orchestration. `analysis_service` runs rules over data and aggregates confidence; `backtest_service` replays the same pipeline over history. External needs declared as Protocols in `ports.py`.
- **infrastructure/** — adapters. `data/` (YFinanceProvider), `cli/` (typer), `ui/` (Streamlit).
- **config/** — pydantic-settings; env precedence: env vars > .env > defaults (prefix `LW_`).

## Knowledge pipeline (local-only)

The rule definitions live in `docs/sistema.md`, a local-only spec that is gitignored and never
distributed; raw working notes live under `docs/extraction/` (also gitignored). Code references
rules exclusively by opaque IDs. Mechanical rules become deterministic functions; semi-mechanical
rules become parameterized heuristics; discretionary rules only contribute to confidence scoring,
never to entry/exit triggers.

## Validation (eval/)

Backtesting harness with deterministic scoring: golden scenario sets (ticker + as-of date windows),
signal-level checks (did the signal fire? did price reach target before stop?), metrics stratified
per rule ID (hit rate, profit factor, max drawdown), timestamped run dirs with config + metrics + report.
No look-ahead: the analysis at date T only sees bars <= T.

## Confidence model

A pick's confidence aggregates only rule-derived evidence: how many independent rules fired,
pattern quality (how far from boundary thresholds), and the spec's own reliability statements
per pattern. The weighting scheme lives in `application/analysis_service` and is tuned exclusively
via backtest results, never hand-waved.
