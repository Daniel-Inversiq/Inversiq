"""
tests/test_workflow_skeletons.py

Tests for roofing (area-based pricing + intake-completeness review) and solar (skeleton).

Roofing pricing logic:
  default lead (no intake_payload) → 80 m² × €48/m² = €3840.00
  pitched 120 m²                   → 120 × €48 = €5760.00
  flat 120 m²                      → 120 × €58 = €6960.00
  tiny area below minimum          → minimum €800.00

Roofing review logic:
  intake has roof_area_m2          → needs_review=False
  intake missing roof_area_m2      → needs_review=True, reason="roof_area_missing_from_intake"
  lead.square_meters fallback only → needs_review=True (area not from intake)

Lead and db are fake — prepare_assets_fn functions accept None for db.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from inversiq.engine.facade import compute_quote_for_lead_v15
from app.verticals.roofing.workflow import ROOFING_VERTICAL
from app.verticals.solar.workflow import SOLAR_VERTICAL


def _fake_lead(
    lead_id: str = "lead-skeleton-1",
    tenant_id: str = "tenant-skeleton-1",
    intake_payload: str | None = None,
    square_meters: float | None = None,
):
    return SimpleNamespace(
        id=lead_id,
        tenant_id=tenant_id,
        intake_payload=intake_payload,
        square_meters=square_meters,
    )


def _intake(**kwargs) -> str:
    """Serialize kwargs as a JSON intake_payload string."""
    return json.dumps(kwargs)


# ---------------------------------------------------------------------------
# Roofing — area-based pricing
# ---------------------------------------------------------------------------

class TestRoofingWorkflow:
    def test_runs_end_to_end(self):
        # Complete intake: roof_area_m2 provided → price is reliable → no review needed.
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["estimate_json"]["workflow"] == "roofing"
        assert result["estimate_json"]["total_eur"] == 3840.00
        assert result["estimate_html_key"].startswith("roofing/")
        assert result["needs_review"] is False
        assert result["engine_status"] == "SUCCEEDED"

    def test_trace_id_is_set(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert isinstance(result["trace_id"], str) and result["trace_id"]

    def test_available_steps_matches_config(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert set(result["available_steps"]) == {"estimate", "review", "store"}

    def test_pitched_roof_area_from_intake(self):
        # 120 m² pitched → 120 × 48 = 5760
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=120, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        est = result["estimate_json"]
        assert est["total_eur"] == 5760.00
        assert est["meta"]["roof_type"] == "pitched"
        assert est["meta"]["roof_area_m2"] == 120.0

    def test_flat_roof_area_from_intake(self):
        # 120 m² flat → 120 × 58 = 6960
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=120, roof_type="flat"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        est = result["estimate_json"]
        assert est["total_eur"] == 6960.00
        assert est["meta"]["roof_type"] == "flat"

    def test_minimum_total_floor_applied(self):
        # 10 m² × 48 = 480 < minimum 800 → total should be 800
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=10, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["estimate_json"]["total_eur"] == 800.00

    def test_square_meters_fallback(self):
        # No intake_payload, but lead.square_meters = 100 → 100 × 48 = 4800
        lead = _fake_lead(square_meters=100.0)
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["estimate_json"]["total_eur"] == 4800.00

    def test_unknown_roof_type_falls_back_to_pitched(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80, roof_type="thatched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        est = result["estimate_json"]
        assert est["meta"]["roof_type"] == "pitched"
        assert est["total_eur"] == 3840.00

    def test_estimate_has_line_items(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        lis = result["estimate_json"]["line_items"]
        assert isinstance(lis, list) and len(lis) == 1
        assert lis[0]["code"] == "roofing_labor_materials"
        assert lis[0]["unit"] == "m2"

    def test_estimate_currency_is_eur(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["estimate_json"]["currency"] == "EUR"

    # --- rendered_text ---

    def test_rendered_text_present(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert isinstance(rt, str) and rt

    def test_rendered_text_contains_key_facts(self):
        # 120 m² flat → 120 × 58 = 6960
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=120, roof_type="flat"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "ROOFING ESTIMATE" in rt
        assert "120" in rt               # area
        assert "58.00" in rt             # rate
        assert "6960.00" in rt           # total
        assert "TOTAL" in rt

    def test_rendered_text_shows_minimum_note_when_floor_applied(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=10, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "minimum charge applied" in rt
        assert "800.00" in rt

    def test_rendered_text_shows_note_when_area_not_from_intake(self):
        # No intake_payload → fallback area → note line should appear
        result = compute_quote_for_lead_v15(db=None, lead=_fake_lead(), vertical=ROOFING_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "area not provided" in rt

    def test_rendered_text_no_note_when_area_from_intake(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "area not provided" not in rt

    # --- Summary string ---

    def test_summary_present(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert isinstance(result["estimate_json"]["summary"], str)
        assert result["estimate_json"]["summary"]  # non-empty

    def test_summary_contains_area_type_and_total(self):
        # 100 m² flat → 100 × 58 = 5800
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=100, roof_type="flat"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "100" in summary          # area
        assert "flat" in summary         # roof type
        assert "5800.00" in summary      # total

    def test_summary_contains_rate_when_no_minimum(self):
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=80, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "48.00" in summary        # rate per m²
        assert "minimum" not in summary

    def test_summary_mentions_minimum_when_floor_applied(self):
        # 10 m² → computed 480 < floor 800 → minimum applied
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=10, roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "minimum" in summary
        assert "800.00" in summary

    def test_minimum_applied_flag_in_meta(self):
        lead_small = _fake_lead(intake_payload=_intake(roof_area_m2=10))
        lead_normal = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        r_small = compute_quote_for_lead_v15(db=None, lead=lead_small, vertical=ROOFING_VERTICAL)
        r_normal = compute_quote_for_lead_v15(db=None, lead=lead_normal, vertical=ROOFING_VERTICAL)
        assert r_small["estimate_json"]["meta"]["minimum_applied"] is True
        assert r_normal["estimate_json"]["meta"]["minimum_applied"] is False

    # --- Review logic ---

    def test_no_intake_triggers_review(self):
        # No intake_payload at all → area is from rules default → needs review.
        result = compute_quote_for_lead_v15(
            db=None, lead=_fake_lead(), vertical=ROOFING_VERTICAL
        )
        assert result["needs_review"] is True

    def test_missing_area_in_intake_triggers_review(self):
        # Intake exists but roof_area_m2 is absent → fallback area → needs review.
        lead = _fake_lead(intake_payload=_intake(roof_type="pitched"))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["needs_review"] is True

    def test_square_meters_fallback_triggers_review(self):
        # lead.square_meters is used, not intake → area_from_intake=False → review.
        lead = _fake_lead(square_meters=90.0)
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["needs_review"] is True

    def test_area_in_intake_suppresses_review(self):
        # roof_area_m2 explicitly in intake → area_from_intake=True → no review.
        lead = _fake_lead(intake_payload=_intake(roof_area_m2=95))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=ROOFING_VERTICAL)
        assert result["needs_review"] is False

    def test_area_from_intake_flag_in_meta(self):
        # Verify the flag itself is recorded correctly in both cases.
        lead_with = _fake_lead(intake_payload=_intake(roof_area_m2=80))
        lead_without = _fake_lead()
        r_with = compute_quote_for_lead_v15(db=None, lead=lead_with, vertical=ROOFING_VERTICAL)
        r_without = compute_quote_for_lead_v15(db=None, lead=lead_without, vertical=ROOFING_VERTICAL)
        assert r_with["estimate_json"]["meta"]["area_from_intake"] is True
        assert r_without["estimate_json"]["meta"]["area_from_intake"] is False


# ---------------------------------------------------------------------------
# Solar — kWp-based pricing
#
# Pricing: system_kw × €1,500/kWp, minimum €3,000
#   default lead (no intake)  → 5.0 kWp × €1,500 = €7,500
#   intake system_kw=8        → 8.0 × €1,500      = €12,000
#   tiny system below minimum → minimum €3,000
# ---------------------------------------------------------------------------

class TestSolarWorkflow:
    def test_runs_end_to_end(self):
        # Complete intake: system_kw provided → price is reliable → no review needed.
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["estimate_json"]["workflow"] == "solar"
        assert result["estimate_json"]["total_eur"] == 7500.00
        assert result["estimate_html_key"].startswith("solar/")
        assert result["engine_status"] == "SUCCEEDED"

    def test_trace_id_is_set(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert isinstance(result["trace_id"], str) and result["trace_id"]

    def test_available_steps_matches_config(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert set(result["available_steps"]) == {"quote", "review", "save"}

    def test_solar_step_ids_differ_from_painting(self):
        """Explicit guard: solar uses different step IDs and the facade handles it."""
        assert SOLAR_VERTICAL.output_step_id == "quote"
        assert SOLAR_VERTICAL.store_html_step_id == "save"
        assert SOLAR_VERTICAL.needs_review_step_id == "review"

    def test_system_kw_from_intake(self):
        # 8 kWp → 8 × 1500 = 12000
        lead = _fake_lead(intake_payload=_intake(system_kw=8.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        est = result["estimate_json"]
        assert est["total_eur"] == 12000.00
        assert est["system_kw"] == 8.0
        assert est["meta"]["kw_from_intake"] is True

    def test_default_system_kw_when_no_intake(self):
        # No intake → rules default 5.0 kWp × 1500 = 7500
        result = compute_quote_for_lead_v15(db=None, lead=_fake_lead(), vertical=SOLAR_VERTICAL)
        est = result["estimate_json"]
        assert est["total_eur"] == 7500.00
        assert est["system_kw"] == 5.0
        assert est["meta"]["kw_from_intake"] is False

    def test_minimum_total_floor_applied(self):
        # 1.0 kWp × 1500 = 1500 < minimum 3000 → total should be 3000
        lead = _fake_lead(intake_payload=_intake(system_kw=1.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["estimate_json"]["total_eur"] == 3000.00
        assert result["estimate_json"]["meta"]["minimum_applied"] is True

    def test_no_minimum_for_normal_system(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["estimate_json"]["meta"]["minimum_applied"] is False

    def test_estimate_has_line_items(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=6.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        lis = result["estimate_json"]["line_items"]
        assert isinstance(lis, list) and len(lis) == 1
        assert lis[0]["code"] == "solar_installation"
        assert lis[0]["unit"] == "kWp"

    def test_estimate_currency_is_eur(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["estimate_json"]["currency"] == "EUR"

    def test_estimate_has_solar_fields(self):
        """Solar-specific fields are present in the output."""
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert "system_kw" in result["estimate_json"]
        assert "workflow" in result["estimate_json"]

    # --- Summary string ---

    def test_summary_present(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert isinstance(result["estimate_json"]["summary"], str)
        assert result["estimate_json"]["summary"]

    def test_summary_contains_kw_and_total(self):
        # 8 kWp × 1500 = 12000
        lead = _fake_lead(intake_payload=_intake(system_kw=8.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "8.0" in summary          # system size
        assert "12000.00" in summary     # total

    def test_summary_contains_rate_when_no_minimum(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "1500.00" in summary      # rate per kWp
        assert "minimum" not in summary

    def test_summary_mentions_minimum_when_floor_applied(self):
        # 1 kWp × 1500 = 1500 < floor 3000 → minimum applied
        lead = _fake_lead(intake_payload=_intake(system_kw=1.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        summary = result["estimate_json"]["summary"]
        assert "minimum" in summary
        assert "3000.00" in summary

    # --- rendered_text ---

    def test_rendered_text_present(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert isinstance(rt, str) and rt

    def test_rendered_text_contains_key_facts(self):
        # 6 kWp × 1500 = 9000
        lead = _fake_lead(intake_payload=_intake(system_kw=6.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "SOLAR ESTIMATE" in rt
        assert "6.0" in rt          # system size
        assert "1500.00" in rt      # rate
        assert "9000.00" in rt      # total
        assert "TOTAL" in rt

    def test_rendered_text_shows_minimum_note_when_floor_applied(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=1.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "minimum charge applied" in rt
        assert "3000.00" in rt

    def test_rendered_text_shows_note_when_kw_not_from_intake(self):
        result = compute_quote_for_lead_v15(db=None, lead=_fake_lead(), vertical=SOLAR_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "system size not provided" in rt

    def test_rendered_text_no_note_when_kw_from_intake(self):
        lead = _fake_lead(intake_payload=_intake(system_kw=5.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        rt = result["estimate_json"]["rendered_text"]
        assert "system size not provided" not in rt

    # --- Review logic ---

    def test_no_intake_triggers_review(self):
        # No intake_payload → system_kw from rules default → needs review.
        result = compute_quote_for_lead_v15(db=None, lead=_fake_lead(), vertical=SOLAR_VERTICAL)
        assert result["needs_review"] is True

    def test_missing_kw_in_intake_triggers_review(self):
        # Intake exists but system_kw absent → fallback → needs review.
        lead = _fake_lead(intake_payload=_intake(roof_type="pitched"))  # unrelated field
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["needs_review"] is True

    def test_kw_in_intake_suppresses_review(self):
        # system_kw explicitly in intake → kw_from_intake=True → no review.
        lead = _fake_lead(intake_payload=_intake(system_kw=6.0))
        result = compute_quote_for_lead_v15(db=None, lead=lead, vertical=SOLAR_VERTICAL)
        assert result["needs_review"] is False

    def test_kw_from_intake_flag_in_meta(self):
        lead_with = _fake_lead(intake_payload=_intake(system_kw=5.0))
        lead_without = _fake_lead()
        r_with = compute_quote_for_lead_v15(db=None, lead=lead_with, vertical=SOLAR_VERTICAL)
        r_without = compute_quote_for_lead_v15(db=None, lead=lead_without, vertical=SOLAR_VERTICAL)
        assert r_with["estimate_json"]["meta"]["kw_from_intake"] is True
        assert r_without["estimate_json"]["meta"]["kw_from_intake"] is False
