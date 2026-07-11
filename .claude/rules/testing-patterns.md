---
paths:
  - "tests/**"
---

# Testing patterns

- Three tiers, directory == marker: `tests/unit` (fast, no I/O), `tests/integration` (network/market data), `tests/e2e` (full pipeline).
- Every rule module in `domain/rules/` gets unit tests with synthetic OHLCV fixtures that construct the exact pattern the rule detects: one happy path plus each boundary violation (e.g. wave 2 retracing exactly 100%).
- Synthetic fixtures live in `tests/fixtures/` as builder functions, not static files, so boundaries are parameterizable.
- Mock only external providers (network, market data); never mock domain logic.
- Naming `test_<feature>_<case>`, group in `Test*` classes, AAA structure, `pytest.mark.parametrize` for case families.
- Verification loop: `make test-quick` then `make quality`.
