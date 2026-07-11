"""The codified trading rules, one module per pattern family.

Every function here implements a rule from the local-only spec (docs/sistema.md,
gitignored) and carries its rule ID. Do not add trading logic that does not trace
back to a spec rule, and never quote spec contents here - opaque IDs only.
"""
