---
paths:
  - "src/**"
---

# Clean architecture

Dependencies point inward only:

```
infrastructure  ->  application  ->  domain        (config is a leaf, importable anywhere)
```

- `domain/` never imports from `application/` or `infrastructure/`, and has no third-party deps beyond pydantic/numpy/pandas.
- `application/` services define their external needs as Protocols in `ports.py`; `infrastructure/` provides the adapters.
- Where new code goes:
  - A trading rule from the spec -> `domain/rules/` (tagged with its rule ID from the local-only `docs/sistema.md`).
  - Swing/wave/pattern data structures -> `domain/value_objects/` or `domain/entities/`.
  - Orchestration (run rules over data, aggregate confidence) -> `application/`.
  - Data sources, CLI, UI, caching -> `infrastructure/`.
- Trading logic MUST trace to a rule ID in `docs/sistema.md` (local-only, gitignored). If a needed rule is missing there, stop and flag it instead of inventing behavior. Never quote spec contents or provenance in tracked files — opaque rule IDs only.
