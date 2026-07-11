"""Neutral market-structure algorithms (no trading opinions): swing detection, wave segmentation.

These are prerequisites the rules engine builds on; trading logic itself lives in domain/rules.
"""

from little_warren.domain.analysis.swings import detect_swings

__all__ = ["detect_swings"]
