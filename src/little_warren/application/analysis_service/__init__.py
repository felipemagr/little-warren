"""Analysis service: run the rules engine over market data and produce Picks.

Pipeline (built once docs/sistema.md exists):
  OHLCV -> swing detection -> wave/pattern classification (domain.rules)
        -> signal aggregation -> Pick(entry, stop, confidence, rules_fired)
"""
