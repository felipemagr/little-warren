"""Impulse classification: the FND elementary rules from the spec.

Implements FND-03..FND-15 (the essential construction rules) and the FND-10
AND-gate: a five-wave sequence is an impulse only if every essential rule
holds; one violation makes it corrective by default. The single exception is
overlap (FND-15): if ONLY that rule fails, the formation is a terminal
impulse rather than corrective.

Same-degree filtering (FND-02) is a segmentation concern and happens before
this module is called.
"""

from pydantic import BaseModel, ConfigDict

from little_warren.domain.value_objects.wave import Wave

FIB_EXTENSION_RATIO = 1.618
"""FND-11: extended wave amplitude >= 161.8% of the next-longest impulse wave."""

MIN_FIFTH_TO_FOURTH_RATIO = 0.382
"""FND-08: wave 5 price range must reach at least 38.2% of wave 4's."""

ALTERNATION_TOLERANCE = 0.10
"""ASSUMED (spec gap): minimum relative difference for waves 2 and 4 to 'differ'
in an aspect under FND-12. The spec defines no numeric threshold; tune via backtest."""

ESSENTIAL_RULES = ("FND-03", "FND-04", "FND-05", "FND-06", "FND-07", "FND-08", "FND-09", "FND-11", "FND-12")
OVERLAP_RULE = "FND-15"


class RuleCheck(BaseModel):
    """Outcome of one spec rule evaluated against a wave sequence."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    passed: bool
    detail: str


class ImpulseAssessment(BaseModel):
    """Result of classifying a five-wave sequence."""

    model_config = ConfigDict(frozen=True)

    is_impulse: bool
    is_terminal: bool
    extended_wave: int | None
    fifth_failure: bool
    checks: list[RuleCheck]

    @property
    def failed_rules(self) -> list[str]:
        return [check.rule_id for check in self.checks if not check.passed]


def classify_impulse(waves: list[Wave]) -> ImpulseAssessment:
    """Classify a five-wave sequence as impulse (tendential or terminal) or corrective.

    Waves must be five alternating same-degree legs, wave 1 first.
    """
    if len(waves) != 5:
        check = RuleCheck(rule_id="FND-03", passed=False, detail=f"need exactly 5 segments, got {len(waves)}")
        return ImpulseAssessment(
            is_impulse=False, is_terminal=False, extended_wave=None, fifth_failure=False, checks=[check]
        )

    w1, w2, w3, w4, w5 = waves
    extended = _extended_wave(w1, w3, w5)

    checks = [
        RuleCheck(rule_id="FND-03", passed=True, detail="5 segments present"),
        _check_directions(waves),
        _check_retracement("FND-05", retracing=w2, of=w1, labels=(2, 1)),
        RuleCheck(
            rule_id="FND-06",
            passed=w3.price_range > w2.price_range,
            detail=f"P(3)={w3.price_range:g} vs P(2)={w2.price_range:g}",
        ),
        _check_retracement("FND-07", retracing=w4, of=w3, labels=(4, 3)),
        RuleCheck(
            rule_id="FND-08",
            passed=w5.price_range >= MIN_FIFTH_TO_FOURTH_RATIO * w4.price_range,
            detail=f"P(5)={w5.price_range:g} vs 38.2% of P(4)={MIN_FIFTH_TO_FOURTH_RATIO * w4.price_range:g}",
        ),
        RuleCheck(
            rule_id="FND-09",
            passed=not (w3.price_range < w1.price_range and w3.price_range < w5.price_range),
            detail=f"P(1)={w1.price_range:g}, P(3)={w3.price_range:g}, P(5)={w5.price_range:g}",
        ),
        RuleCheck(
            rule_id="FND-11",
            passed=extended is not None,
            detail=f"extended wave: {extended if extended else 'none reaches 161.8% of next-longest'}",
        ),
        _check_alternation(w1, w2, w3, w4),
        _check_overlap(w2, w4),
    ]

    failures = {check.rule_id for check in checks if not check.passed}
    essential_ok = failures.isdisjoint(ESSENTIAL_RULES)
    overlap_failed = OVERLAP_RULE in failures

    is_impulse = essential_ok
    is_terminal = essential_ok and overlap_failed
    fifth_failure = is_impulse and w5.price_range < w4.price_range

    return ImpulseAssessment(
        is_impulse=is_impulse,
        is_terminal=is_terminal,
        extended_wave=extended if is_impulse else None,
        fifth_failure=fifth_failure,
        checks=checks,
    )


def _check_directions(waves: list[Wave]) -> RuleCheck:
    """FND-04: waves 1/3/5 push with the trend, 2/4 against it."""
    trend_up = waves[0].is_up
    expected = [trend_up, not trend_up, trend_up, not trend_up, trend_up]
    passed = [wave.is_up for wave in waves] == expected
    return RuleCheck(rule_id="FND-04", passed=passed, detail="impulse legs alternate with 1/3/5 in trend direction")


def _check_retracement(rule_id: str, retracing: Wave, of: Wave, labels: tuple[int, int]) -> RuleCheck:
    """FND-05 / FND-07: a corrective wave never retraces 100% of the prior impulse wave."""
    ratio = retracing.retracement_of(of)
    return RuleCheck(
        rule_id=rule_id,
        passed=ratio < 1.0,
        detail=f"wave {labels[0]} retraces {ratio:.1%} of wave {labels[1]}",
    )


def _extended_wave(w1: Wave, w3: Wave, w5: Wave) -> int | None:
    """FND-11: exactly one impulse wave with amplitude >= 161.8% of the next-longest."""
    amplitudes = {1: w1.price_range, 3: w3.price_range, 5: w5.price_range}
    ordered = sorted(amplitudes.items(), key=lambda item: item[1], reverse=True)
    (longest_wave, longest), (_, second) = ordered[0], ordered[1]
    if second > 0 and longest >= FIB_EXTENSION_RATIO * second:
        return longest_wave
    return None


def _differs(a: float, b: float, tolerance: float = ALTERNATION_TOLERANCE) -> bool:
    reference = max(abs(a), abs(b))
    if reference == 0:
        return False
    return abs(a - b) / reference > tolerance


def _check_alternation(w1: Wave, w2: Wave, w3: Wave, w4: Wave) -> RuleCheck:
    """FND-12: waves 2 and 4 must differ in price range, time or intensity.

    Subdivision-count and construction aspects need sub-wave data not available
    at this degree, so this check covers the three measurable aspects.
    """
    aspects = {
        "price": _differs(w2.price_range, w4.price_range),
        "time": _differs(float(w2.duration), float(w4.duration)),
        "intensity": _differs(w2.retracement_of(w1), w4.retracement_of(w3)),
    }
    differing = [name for name, differs in aspects.items() if differs]
    return RuleCheck(
        rule_id="FND-12",
        passed=bool(differing),
        detail=f"differing aspects: {differing or 'none'}",
    )


def _check_overlap(w2: Wave, w4: Wave) -> RuleCheck:
    """FND-15: in a tendential impulse no part of wave 4 enters wave 2's price range."""
    overlap = min(w2.high, w4.high) - max(w2.low, w4.low)
    return RuleCheck(
        rule_id="FND-15",
        passed=overlap <= 0,
        detail=f"wave 4 [{w4.low:g}, {w4.high:g}] vs wave 2 [{w2.low:g}, {w2.high:g}]",
    )
