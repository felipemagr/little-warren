# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

little-warren is a rules-based stock analysis engine: it runs a deterministic set of technical-analysis rules over market data and outputs the best picks with stop levels and a confidence score, validated by backtesting on historical time series.

The trading rules are defined in a **local-only spec: `docs/sistema.md`** (gitignored, never committed). That file is the single source of truth. Never invent trading logic: every rule in code must trace back to a rule ID in the spec.

**Confidentiality rule: the contents and provenance of `docs/` (the spec, extraction notes, PDFs) must never appear in tracked files, code comments, commit messages or PRs — reference rules by their opaque IDs only.**

## Quick reference

```bash
make dev                # uv sync with dev+test+ui groups
make test               # full pytest suite
make test-unit          # fast unit tests
make test-quick         # fail-fast unit tests
make quality            # ruff lint + format — ALWAYS run before committing
make ui                 # Streamlit UI
uv add <pkg>            # add a dependency (never pip)
```

## Architecture (clean, 3 layers, dependencies point inward)

```
infrastructure  →  application  →  domain        (config is a leaf)
```

- `domain/` — pure logic, no external deps: entities (`Pick`, `Signal`), value objects, and `rules/` (the codified rules, one module per pattern family, each rule tagged with its spec ID).
- `application/` — services orchestrating domain logic: `analysis_service` (run rules over market data → picks), `backtest_service`.
- `infrastructure/` — the outside world: `data/` (yfinance provider), `cli/`, `ui/` (Streamlit).
- `config/` — pydantic-settings `Settings`; env precedence: env vars > `.env` > defaults.

New trading rule → `domain/rules/`. New data source → `infrastructure/data/`. New orchestration → `application/`.

## Testing

Three tiers mapped to directories and markers: `tests/unit` (fast, isolated), `tests/integration` (may hit network/market data), `tests/e2e` (full pipeline). Every rule gets unit tests with synthetic OHLCV fixtures that construct the exact pattern the rule detects — one happy path + boundary violations.

## Code style

- Ruff is the only linter/formatter (line 119, double quotes, Google docstrings). Run `make quality` before committing.
- Modern typing (`X | None`), absolute imports, early returns, exception chaining (`raise ... from e`).
- No em dashes or emoji in code.

## Git

- Personal repo: remote uses the `github.com-personal` SSH alias → personal key (`~/.ssh/id_ed25519_personal`). Never switch it to a work identity.
- Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`).
- Never commit anything gitignored under `docs/` — it is the local knowledge base.
