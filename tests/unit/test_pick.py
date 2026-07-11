"""Unit tests for the Pick entity."""

from datetime import date

import pytest
from pydantic import ValidationError

from little_warren.domain.entities import Direction, Pick

pytestmark = pytest.mark.unit


def make_pick(**overrides) -> Pick:
    base = {
        "ticker": "SAN.MC",
        "as_of": date(2026, 7, 10),
        "direction": Direction.LONG,
        "entry": 10.0,
        "stop": 9.5,
        "confidence": 0.7,
        "rules_fired": ["R-001"],
    }
    return Pick(**{**base, **overrides})


class TestPickValidation:
    def test_valid_long(self):
        pick = make_pick()
        assert pick.risk_per_unit == pytest.approx(0.5)

    def test_valid_short(self):
        pick = make_pick(direction=Direction.SHORT, entry=10.0, stop=10.5)
        assert pick.risk_per_unit == pytest.approx(0.5)

    def test_long_stop_above_entry_rejected(self):
        with pytest.raises(ValidationError, match="stop < entry"):
            make_pick(stop=10.5)

    def test_short_stop_below_entry_rejected(self):
        with pytest.raises(ValidationError, match="stop > entry"):
            make_pick(direction=Direction.SHORT, stop=9.5)

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_out_of_bounds_rejected(self, confidence):
        with pytest.raises(ValidationError):
            make_pick(confidence=confidence)

    def test_rules_fired_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            make_pick(rules_fired=[])
