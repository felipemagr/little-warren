"""Backtest service: replay the rules engine over history and measure precision.

Drives the same analysis pipeline the UI uses (no separate logic) over
historical windows; the eval/ harness consumes it to produce metrics
(hit rate, profit factor, drawdown) per rule and aggregate.
"""
