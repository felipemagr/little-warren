"""Unit tests for the FND impulse classifier (rule IDs reference the local spec)."""

import pytest

from little_warren.domain.rules.impulse import classify_impulse
from tests.fixtures.synthetic import waves_from_prices

pytestmark = pytest.mark.unit

# Canonical valid up-impulse with 3rd wave extended:
# P(1)=20, P(2)=10 (50% retr), P(3)=40 (>= 161.8% of P(5)=22), P(4)=12 (30% retr), P(5)=22.
VALID_X3 = [100, 120, 110, 150, 138, 160]


class TestValidImpulses:
    def test_canonical_x3_impulse(self):
        result = classify_impulse(waves_from_prices(VALID_X3, bars_per_leg=[5, 3, 8, 5, 5]))

        assert result.is_impulse
        assert not result.is_terminal
        assert result.extended_wave == 3
        assert not result.fifth_failure
        assert result.failed_rules == []

    def test_down_impulse_mirrors(self):
        prices = [round(200 - (p - 100), 4) for p in VALID_X3]  # mirror around 200

        result = classify_impulse(waves_from_prices(prices, bars_per_leg=[5, 3, 8, 5, 5]))

        assert result.is_impulse
        assert result.extended_wave == 3

    def test_terminal_impulse_when_only_overlap_fails(self):
        # Wave 4 bottoms at 118, inside wave 2's range [105, 120]; everything else passes.
        prices = [100, 120, 105, 150, 118, 140]

        result = classify_impulse(waves_from_prices(prices, bars_per_leg=[5, 3, 8, 5, 5]))

        assert result.is_impulse
        assert result.is_terminal
        assert result.failed_rules == ["FND-15"]

    def test_fifth_failure_flagged(self):
        # All rules pass but P(5)=10 < P(4)=16 -> "fallo de quinta" candidate (FND-08 note).
        prices = [100, 120, 110, 152, 136, 146]

        result = classify_impulse(waves_from_prices(prices, bars_per_leg=[5, 3, 8, 5, 5]))

        assert result.is_impulse
        assert result.fifth_failure


class TestViolations:
    def test_wrong_wave_count_fails_fnd03(self):
        result = classify_impulse(waves_from_prices([100, 120, 110, 150]))

        assert not result.is_impulse
        assert result.failed_rules == ["FND-03"]

    def test_full_wave2_retracement_fails_fnd05(self):
        result = classify_impulse(waves_from_prices([100, 120, 100, 150, 138, 160]))

        assert not result.is_impulse
        assert "FND-05" in result.failed_rules

    def test_wave3_shorter_than_wave2_fails_fnd06(self):
        result = classify_impulse(waves_from_prices([100, 120, 108, 117, 112, 130]))

        assert not result.is_impulse
        assert "FND-06" in result.failed_rules

    def test_full_wave4_retracement_fails_fnd07(self):
        result = classify_impulse(waves_from_prices([100, 120, 110, 150, 110, 160]))

        assert not result.is_impulse
        assert "FND-07" in result.failed_rules

    def test_tiny_fifth_fails_fnd08(self):
        # P(4)=16 -> minimum admissible P(5) = 6.112; give it 5.
        result = classify_impulse(waves_from_prices([100, 120, 110, 150, 134, 139]))

        assert not result.is_impulse
        assert "FND-08" in result.failed_rules

    def test_fifth_just_above_382_boundary_passes_fnd08(self):
        # P(4)=16 -> 38.2% = 6.112; P(5)=6.2 sits just above the minimum.
        result = classify_impulse(waves_from_prices([100, 120, 110, 150, 134, 140.2]))

        assert "FND-08" not in result.failed_rules

    def test_wave3_shortest_fails_fnd09(self):
        # P(1)=20, P(3)=15, P(5)=18: wave 3 strictly the shortest.
        result = classify_impulse(waves_from_prices([100, 120, 112, 127, 117, 135]))

        assert not result.is_impulse
        assert "FND-09" in result.failed_rules

    def test_no_extension_fails_fnd11(self):
        # P(1)=20, P(3)=22, P(5)=21: longest < 161.8% of next-longest.
        result = classify_impulse(waves_from_prices([100, 120, 110, 132, 120, 141]))

        assert not result.is_impulse
        assert "FND-11" in result.failed_rules
        assert result.extended_wave is None

    def test_extension_just_above_1618_boundary_passes_fnd11(self):
        # P(5)=20 -> extension needs >= 32.36; P(3)=32.4 sits just above.
        result = classify_impulse(waves_from_prices([100, 120, 110, 142.4, 130, 150], bars_per_leg=[5, 3, 8, 5, 5]))

        assert "FND-11" not in result.failed_rules
        assert result.extended_wave == 3

    def test_identical_waves_2_and_4_fail_alternation_fnd12(self):
        # Same price range (10), same duration, near-identical intensity.
        result = classify_impulse(waves_from_prices([100, 120, 110, 130, 120, 156]))

        assert not result.is_impulse
        assert "FND-12" in result.failed_rules

    def test_non_alternating_legs_fail_fnd04(self):
        waves = waves_from_prices(VALID_X3, bars_per_leg=[5, 3, 8, 5, 5])
        broken = [waves[0], waves[1], waves[2], waves[4], waves[3]]  # scrambled order

        result = classify_impulse(broken)

        assert not result.is_impulse
