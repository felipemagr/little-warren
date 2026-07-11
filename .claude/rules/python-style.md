---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "eval/**/*.py"
---

# Python style

- Absolute imports only (`from little_warren.domain...`), never relative.
- Modern typing: `X | None`, builtin generics (`list[str]`), `StrEnum` for enums.
- Exception chaining: `raise ... from e`; raise specific exceptions with actionable messages.
- Early returns over nested conditionals.
- Loguru for logging with lazy formatting (`logger.info("x={}", x)`), never f-strings in log calls.
- Google-style docstrings, lean: one summary line; args/returns only when non-obvious.
- No em dashes or emoji in code or comments.
- uv only: `uv add <pkg>`, `uv run <cmd>`. Never pip, never edit uv.lock by hand.
- Pandas: OHLCV frames use lowercase columns open/high/low/close/volume indexed by timestamp — every function can rely on this contract.
