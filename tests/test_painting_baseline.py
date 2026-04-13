"""
tests/test_painting_baseline.py

Phase 0 safety baseline for the painting (paintly) pricing flow.

These tests characterize *existing behavior* — they are parity/regression tests,
not specification tests. Their job is to catch breakage during future refactoring.

Scope:
  - price_from_vision     : core EU pricing math (pure function, no DB)
  - needs_review_from_output : routing decision (pure function, no DB)
  - build_pricing_output  : output builder with a minimal mock lead (no DB)

All three functions are pure or near-pure; tests here need no fixtures,
no HTTP client, and no database connection.
"""
from __future__ import annotations

import json
import types
from decimal import Decimal
from typing import Any, Dict

import pytest

from app.verticals.painting.needs_review import needs_review_from_output
from app.verticals.painting.pricing_engine_us import (
    load_rules_eu,
    price_from_vision,
    run_pricing_engine,
)
from app.verticals.painting.pricing_output_builder import build_pricing_output

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

RULES_EU = load_rules_eu()


def _lead(*, id: str = "lead-baseline-1", square_meters=None, intake_payload=None):
    """Minimal mock lead that satisfies what the pricing functions inspect via getattr."""
    return types.SimpleNamespace(
        id=id,
        square_meters=square_meters,
        intake_payload=intake_payload,
    )


def _clean_estimate(total: float, area_sqm: float = 50.0) -> Dict[str, Any]:
    """
    Minimal well-formed estimate dict (as if returned by build_pricing_output).
    Used to drive needs_review_from_output tests.
    """
    return {
        "totals": {"grand_total": total, "pre_tax": total},
        "line_items": [
            {
                "code": "walls",
                "label": "Wanden schilderen",
                "quantity": area_sqm,
                "unit": "sqm",
                "unit_price": total / area_sqm,
                "total": total,
                "category": "labor",
            }
        ],
        "meta": {},
        "total_eur": str(total),
    }


# ---------------------------------------------------------------------------
# 1. price_from_vision — EU pricing math
#
# Formula (EU rules, walls):
#   base_total = area_sqm * 18
#   labor_multiplier = prep_mult * access_mult * complexity_mult * job_type_mult
#   labor_eur = base_total * labor_multiplier * 0.70   (labor_ratio)
#   materials_eur = base_total * 0.30                   (materials_ratio)
#   cost_eur = labor_eur + materials_eur
#   total_eur = cost_eur * 1.30                         (margin 30%)
# ---------------------------------------------------------------------------


class TestPriceFromVision:

    def test_normal_50sqm_light_prep(self):
        """
        50 m² walls, light prep / low access / low complexity, Binnenwerk.
        All multipliers = 1.0 → simplest possible pricing path.

        Expected:
          base_total = 50 * 18 = 900
          labor_eur  = 900 * 0.70 = 630
          materials  = 900 * 0.30 = 270
          cost       = 900
          total      = 900 * 1.30 = 1170
        """
        surface = {
            "surface_type": "walls",
            "area_sqm": 50.0,
            "prep_level": "light",
            "access_risk": "low",
            "estimated_complexity": 1.0,
            "confidence": 0.90,
            "pricing_ready": True,
        }
        result = price_from_vision(surface, rules=RULES_EU)

        assert result["status"] == "priced_with_margin"
        assert result["base_total_eur"] == pytest.approx(900.0)
        assert result["labor_eur"] == pytest.approx(630.0)
        assert result["materials_eur"] == pytest.approx(270.0)
        assert result["total_eur"] == pytest.approx(1170.0)
        assert result["currency"] == "EUR"
        assert len(result["line_items"]) == 1

    def test_complex_100sqm_medium_prep(self):
        """
        100 m² walls, medium prep / medium access / medium complexity (1.15), Binnenwerk.

        Expected:
          base_total        = 100 * 18 = 1800
          labor_multiplier  = 1.25 * 1.15 * 1.20 * 1.0 = 1.725
          labor_cost        = 1800 * 1.725 = 3105
          labor_eur         = 3105 * 0.70 = 2173.50
          materials_eur     = 1800 * 0.30 = 540.00
          cost_eur          = 2713.50
          total_eur         = 2713.50 * 1.30 = 3527.55
        """
        surface = {
            "surface_type": "walls",
            "area_sqm": 100.0,
            "prep_level": "medium",
            "access_risk": "medium",
            "estimated_complexity": 1.15,  # → complexity_bucket "medium" → mult 1.20
            "confidence": 0.85,
            "pricing_ready": True,
        }
        result = price_from_vision(surface, rules=RULES_EU)

        assert result["status"] == "priced_with_margin"
        assert result["base_total_eur"] == pytest.approx(1800.0)
        assert result["total_eur"] == pytest.approx(3527.55, rel=1e-4)

    def test_exterior_heavy_prep_max_multipliers(self):
        """
        80 m² exterior_siding, heavy prep / high access / high complexity (1.3), Buitenwerk.
        All multipliers at maximum → result should be well above 2× the base.

        Expected:
          base_total = 80 * 28 = 2240
          mult = 1.60 * 1.35 * 1.40 * 1.30 = 3.9312
          labor_cost = 2240 * 3.9312 = 8805.89
          labor_eur  = 8805.89 * 0.70 = 6164.12
          materials  = 2240 * 0.30 = 672.00
          cost       = 6836.12
          total      ≈ 8886.96
        """
        surface = {
            "surface_type": "exterior_siding",
            "area_sqm": 80.0,
            "prep_level": "heavy",
            "access_risk": "high",
            "estimated_complexity": 1.3,  # → complexity_bucket "high" → mult 1.40
            "job_type": "Buitenwerk",
            "confidence": 0.80,
            "pricing_ready": True,
        }
        result = price_from_vision(surface, rules=RULES_EU)

        assert result["status"] == "priced_with_margin"
        assert result["total_eur"] == pytest.approx(8886.96, rel=1e-4)
        # Sanity: heavy exterior should comfortably exceed 2× the base rate
        assert result["total_eur"] > result["base_total_eur"] * 2

    def test_zero_area_returns_blocked(self):
        """
        area_sqm = 0 → no surface area to price → pricing_blocked / NO_SURFACE_AREA.
        This protects against silent €0 estimates.
        """
        surface = {
            "surface_type": "walls",
            "area_sqm": 0.0,
            "prep_level": "light",
            "access_risk": "low",
            "estimated_complexity": 1.0,
            "confidence": 0.95,
            "pricing_ready": True,
        }
        result = price_from_vision(surface, rules=RULES_EU)

        assert result["status"] == "pricing_blocked"
        assert result["reason"] == "NO_SURFACE_AREA"

    def test_tenant_minimum_price_floors_the_total(self):
        """
        5 m² (tiny job) would price at ~117 EUR, but tenant minimum is 750 EUR.
        The minimum must win.
        """
        surface = {
            "surface_type": "walls",
            "area_sqm": 5.0,
            "prep_level": "light",
            "access_risk": "low",
            "estimated_complexity": 1.0,
            "confidence": 0.90,
            "pricing_ready": True,
        }
        result = price_from_vision(
            surface, rules=RULES_EU, tenant_pricing={"minimum_price": 750.0}
        )

        assert result["status"] == "priced_with_margin"
        assert result["total_eur"] >= 750.0

    def test_tenant_price_per_m2_replaces_base_rate(self):
        """
        Tenant overrides the per-sqm wall rate (25 EUR vs default 18 EUR).
        base_total must reflect the tenant rate.
        """
        surface = {
            "surface_type": "walls",
            "area_sqm": 50.0,
            "prep_level": "light",
            "access_risk": "low",
            "estimated_complexity": 1.0,
            "confidence": 0.90,
            "pricing_ready": True,
        }
        result = price_from_vision(
            surface, rules=RULES_EU, tenant_pricing={"price_per_m2": 25.0}
        )

        assert result["status"] == "priced_with_margin"
        assert result["base_total_eur"] == pytest.approx(50 * 25.0)

    def test_run_pricing_engine_accepts_quote_inputs_shape(self):
        """
        run_pricing_engine() must handle the quote_inputs dict shape that the
        vision aggregator produces (keys: area, modifiers, pricing_ready, ...).
        """
        lead = _lead(square_meters=60.0)
        quote_inputs = {
            "area": {"value_m2": 60.0, "source": "customer"},
            "modifiers": {"prep_level": "medium", "complexity": 1.0},
            "pricing_ready": True,
            "needs_review": False,
            "review_reasons": [],
            "vision_signal_confidence": 0.85,
        }
        result = run_pricing_engine(lead, quote_inputs, rules=RULES_EU)

        assert result["status"] == "priced_with_margin"
        assert result["total_eur"] > 0


# ---------------------------------------------------------------------------
# 2. needs_review_from_output — routing decision
# ---------------------------------------------------------------------------


class TestNeedsReviewFromOutput:

    def test_clean_estimate_no_review(self):
        """Well-formed estimate with positive total → no review needed."""
        reasons = needs_review_from_output(_clean_estimate(1500.0))
        assert reasons == []

    def test_missing_total_hard_blocks(self):
        """No total field at all → hard blocker 'missing_total'."""
        estimate = {"line_items": [], "meta": {}}
        reasons = needs_review_from_output(estimate)
        assert "missing_total" in reasons

    def test_zero_total_hard_blocks(self):
        """Total of 0 → hard blocker 'non_positive_total'."""
        estimate = {
            "totals": {"grand_total": 0.0, "pre_tax": 0.0},
            "line_items": [],
            "total_eur": "0.0",
            "meta": {},
        }
        reasons = needs_review_from_output(estimate)
        assert "non_positive_total" in reasons

    def test_surface_preparation_required_is_hard_trigger(self):
        """
        surface_preparation_required in vision review reasons is a hard trigger —
        returns immediately with exactly ["vision:surface_preparation_required"].
        """
        estimate = {
            **_clean_estimate(1500.0),
            "meta": {
                "vision_needs_review": True,
                "vision_review_reasons": ["surface_preparation_required"],
            },
        }
        reasons = needs_review_from_output(estimate)
        assert reasons == ["vision:surface_preparation_required"]

    def test_aggregate_surface_preparation_is_hard_trigger(self):
        """
        Same hard trigger via the vision aggregate path (meta.vision_aggregate_*).
        """
        estimate = {
            **_clean_estimate(1500.0),
            "meta": {
                "vision_aggregate_needs_review": True,
                "vision_aggregate_review_reasons": ["surface_preparation_required"],
            },
        }
        reasons = needs_review_from_output(estimate)
        assert reasons == ["vision:surface_preparation_required"]

    def test_single_soft_signal_alone_does_not_trigger_review(self):
        """
        vision_needs_review alone is only 1 soft signal — must NOT trigger review.
        The threshold is 2+ soft signals.
        """
        estimate = {
            **_clean_estimate(1500.0),
            "meta": {"vision_needs_review": True, "vision_review_reasons": []},
        }
        reasons = needs_review_from_output(estimate)
        assert reasons == []

    def test_two_soft_signals_trigger_review(self):
        """
        vision_needs_review + empty line_items = 2 soft signals → triggers review.
        """
        estimate = {
            "totals": {"grand_total": 1500.0, "pre_tax": 1500.0},
            "total_eur": "1500.0",
            "line_items": [],
            "meta": {
                "vision_needs_review": True,
                "vision_review_reasons": [],
            },
        }
        reasons = needs_review_from_output(estimate)
        assert len(reasons) >= 2
        assert "vision_needs_review" in reasons
        assert "no_line_items" in reasons

    def test_very_low_total_and_low_confidence_trigger_review(self):
        """
        Total < 200 (total_very_low) + confidence < 0.45 (confidence_low) = 2 soft signals.
        """
        estimate = {
            **_clean_estimate(150.0),
            "meta": {"confidence": 0.3},
        }
        reasons = needs_review_from_output(estimate)
        assert len(reasons) >= 2
        assert "total_very_low" in reasons
        assert "confidence_low" in reasons


# ---------------------------------------------------------------------------
# 3. build_pricing_output — output builder
# ---------------------------------------------------------------------------


class TestBuildPricingOutput:

    def test_normal_pricing_produces_populated_output(self):
        """
        Pricing dict with total_eur and line_items → output has all key fields.
        """
        lead = _lead(square_meters=50.0)
        vision = {"area_sqm": 50.0}
        pricing = {
            "status": "priced_with_margin",
            "total_eur": 1170.0,
            "labor_eur": 630.0,
            "materials_eur": 270.0,
            "line_items": [
                {
                    "surface_type": "walls",
                    "quantity": 50.0,
                    "unit": "sqm",
                    "unit_price_eur": 18.0,
                    "total_eur": 1170.0,
                    "prep_level": "light",
                    "access_risk": "low",
                }
            ],
        }
        output = build_pricing_output(lead, vision, pricing)

        assert output["total_eur"] is not None
        assert Decimal(output["total_eur"]) > 0
        assert output["currency"] == "EUR"
        assert len(output["line_items"]) >= 1
        assert output["totals"]["grand_total"] > 0

    def test_estimate_range_fallback_uses_high_eur(self):
        """
        When pricing only has estimate_range (no total_eur), the builder falls
        back to the high_eur value and adds a Dutch indicatie note.
        """
        lead = _lead(square_meters=50.0)
        vision = {"area_sqm": 50.0}
        pricing = {
            "status": "needs_review",
            "estimate_range": {"low_eur": 900.0, "high_eur": 1200.0},
        }
        output = build_pricing_output(lead, vision, pricing)

        assert Decimal(output["total_eur"]) == Decimal("1200.0")
        assert any("indicatie" in n.lower() for n in output.get("notes", []))

    def test_empty_pricing_falls_back_to_provisional_minimum(self):
        """
        Completely empty pricing dict → provisional minimum (500 EUR) so the
        estimate never goes out with a missing or zero total.
        """
        output = build_pricing_output(_lead(), {}, {})

        assert Decimal(output["total_eur"]) == Decimal("500.00")
        assert len(output["line_items"]) >= 1
        assert output["line_items"][0]["code"] == "provisional_minimum"

    def test_output_always_has_total_eur_and_currency(self):
        """
        Regardless of input, the output dict must always contain total_eur and
        currency. This is the contract the downstream UI depends on.
        """
        # Run with minimal valid pricing (just a total)
        output = build_pricing_output(
            _lead(square_meters=75.0),
            {"area_sqm": 75.0},
            {"total_eur": 2000.0},
        )
        assert "total_eur" in output
        assert output["total_eur"] is not None
        assert "currency" in output
        assert output["currency"] == "EUR"
