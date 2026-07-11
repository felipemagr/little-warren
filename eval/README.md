# eval/ — backtesting and validation harness

Measures the precision of the codified system on historical time series with fully
deterministic scoring.

Planned layout (built once `domain/rules/` exists):

```
eval/system_backtest/
├── README.md          # doctrine: scenario definition, metrics, no-look-ahead rule
├── schema.py          # pydantic models for scenarios + splits, with lint/leakage checks
├── scenarios.yaml     # golden set: (ticker, as-of window, expected signal or none)
├── splits.yaml        # dev / holdout, subset invariants enforced
└── harness/
    ├── cli.py         # lint | run | compare
    ├── runner.py      # drives application.backtest_service directly (no UI layer)
    ├── scorer.py      # deterministic: did the signal fire? stop hit before target?
    ├── metrics.py     # per-rule-ID and aggregate: hit rate, profit factor, max drawdown
    ├── report.py      # timestamped run dirs: config, metrics.json, report.md
    └── cache.py       # results keyed by (rules_version, ticker, window)
```

Hard rules:
- The analysis at date T may only see bars up to T (no look-ahead).
- Metrics are stratified by rule ID so a regression points at the exact rule.
- Runs are reproducible: rule parameters are versioned, data windows pinned.
