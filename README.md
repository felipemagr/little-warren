# little-warren

Rules-based stock analysis tool. A deterministic technical-analysis engine — pattern classification, confirmation triggers, stops and money management — that analyses market data and surfaces the best picks with stop levels and a confidence score. A backtesting harness validates the engine's precision on historical time series.

## Quick start

```bash
make dev        # install all dependency groups (uv)
make test       # run the test suite
make quality    # lint + format (ruff)
make ui         # launch the Streamlit analysis UI
```

## Repository layout

- `src/little_warren/domain/` — pure business logic: entities, value objects and the trading rules (no external deps)
- `src/little_warren/application/` — services orchestrating the domain: analysis, screening, backtesting
- `src/little_warren/infrastructure/` — adapters: market data providers, cache, CLI, UI
- `eval/` — backtesting/validation harness measuring the engine's precision on historical data
- `tests/` — unit / integration / e2e tiers (pytest markers)

The rule definitions themselves live in a local-only spec (`docs/`, not distributed); code references them by opaque rule IDs.
