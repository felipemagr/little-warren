---
name: scanner
description: Run the little-warren market scanner and interpret its picks. Use whenever the user asks to scan the market, check indices or tickers for signals, find picks, analyze a specific ticker, or backtest one. Also for questions about a pick's entry/stop/target/confidence.
allowed-tools: Bash, Read
---

# Market scanner

Runs the rules engine over any ticker universe and surfaces picks with entry, stop, target and a
calibrated confidence score. All commands run from the repo root with `uv run`.

## Commands

```bash
# Scan whole indices (presets resolve live constituents, cached weekly):
uv run python -m little_warren.infrastructure.cli.main scan --preset "S&P 500"
uv run python -m little_warren.infrastructure.cli.main scan --preset "DAX 40" --preset "IBEX 35" --preset "FTSE 100"

# Scan arbitrary tickers (anything Yahoo Finance serves):
uv run python -m little_warren.infrastructure.cli.main scan CRM NVDA BTC-USD --min-confidence 0.6

# Single ticker deep-dive (current signal, if any) and walk-forward backtest:
uv run python -m little_warren.infrastructure.cli.main analyze CRM
uv run python -m little_warren.infrastructure.cli.main backtest NVDA --days 2500

# The Streamlit UI (same engine, visual):
make ui
```

Presets: "S&P 500", "DAX 40", "FTSE 100", "IBEX 35", "Europe core", "Indices".
A full S&P 500 scan takes a few minutes; run it in the background and report when done.
If the environment is missing, run `make dev` first. Suppress log noise with `2>/dev/null | grep -v INFO`.

## How to interpret and report picks

- **confidence >= 0.70 is the only bucket worth acting on**: validated out-of-sample precision is
  ~78% (three independent 10-year runs, net of 0.15% costs). Below 0.70 is statistically a coin
  flip; the user does not trade those but still wants to SEE them. So scan with `--min-confidence 0`
  and report in two tiers: lead with the >= 0.70 picks in full detail, then list lower-confidence
  ones briefly (ticker, direction, confidence) labeled as curiosity, not actionable.
- **target** = the pattern's minimum price objective; a pick "wins" when price touches the target
  before the stop. It is a minimum, not a ceiling.
- **stop** = invalidation level; **risk per unit** = |entry - stop|. Always compute and report
  reward:risk = |entry - target| / |entry - stop| (typical winners pay ~0.5R; flag anything unusual).
- **Freshness**: picks are one-shot. A signal is actionable the day the scan shows it; if price has
  already run past the target, the trade is over - never suggest chasing.
- **rules** lists the opaque rule IDs that fired (traceability into the local spec `docs/sistema.md`).
- No picks in a scan is NORMAL and expected most days; say so plainly (the system requires every
  condition to hold - FND-25).

## Constraints

- The default parameters ARE the calibrated system; do not change reversal/stop/entry-mode defaults
  without a new backtest calibration (scripts/calibrate.py, scripts/big_validation.py).
- The rule spec and its provenance live gitignored under `docs/` and must never be quoted or named
  in tracked files, commit messages or PRs - opaque rule IDs only (see .claude/rules/git-commits.md).
- This is decision support, not financial advice; report numbers, not exhortations.
