"""
app/verticals/roofing/workflow.py

Roofing workflow — area-based pricing with intake-completeness review.

Pricing logic (step_estimate_v1):
  - Reads roof_area_m2 and roof_type from lead.intake_payload (JSON string).
  - Falls back to lead.square_meters, then rules["default_area_m2"], then 80 m².
  - Looks up rate_eur_per_m2 from rules["base_rates"][roof_type].
  - Applies minimum_total_eur floor from rules.
  - Records area_from_intake in meta (True only when intake had roof_area_m2).
  - Produces a human-readable summary string covering the key price facts.
  - Produces a rendered_text block: a fully formatted plain-text quote ready
    for email body, review card, or PDF without additional parsing.

Review logic (step_review_v1):
  - Marks needs_review=True when area_from_intake is False.
  - Rationale: a fallback area means the price is based on a guess, not a
    customer-supplied measurement. A human should confirm before sending.
  - Populates review_reasons list for downstream use.

Steps:
  roofing.estimate.v1  — area-based pricing from intake_payload + rules
  roofing.review.v1    — flags review when roof area was not in intake
  roofing.store.v1     — returns a fake storage key
"""
from __future__ import annotations

import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from inversiq.engine.config import StepConfig
from inversiq.engine.context import PipelineState, StepContract, StepResult
from inversiq.engine.facade import VerticalDefinition
from inversiq.engine.registry import StepRegistry


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_estimate_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    lead: Any = assets["lead"]
    rules: Dict[str, Any] = assets.get("rules") or {}

    # --- Parse intake payload ---
    intake: Dict[str, Any] = {}
    try:
        raw = getattr(lead, "intake_payload", None)
        if isinstance(raw, str) and raw.strip():
            intake = json.loads(raw)
    except Exception:
        intake = {}

    # --- Roof area: intake > lead.square_meters > rules default > 80 ---
    # area_from_intake is True only when the customer explicitly provided roof_area_m2.
    area_from_intake: bool = intake.get("roof_area_m2") is not None
    roof_area_m2 = 80.0
    try:
        v = intake.get("roof_area_m2") or getattr(lead, "square_meters", None)
        if v is not None:
            roof_area_m2 = float(v)
        elif rules.get("default_area_m2"):
            roof_area_m2 = float(rules["default_area_m2"])
    except Exception:
        pass

    # --- Roof type: intake > "pitched" ---
    roof_type = str(intake.get("roof_type") or "pitched").lower()
    if roof_type not in ("pitched", "flat"):
        roof_type = "pitched"

    # --- Rate lookup ---
    base_rates = rules.get("base_rates") or {}
    rate_info = base_rates.get(roof_type) or {"rate_eur_per_m2": 48.00, "label": "Roofing"}
    rate_eur_per_m2 = float(rate_info.get("rate_eur_per_m2", 48.00))
    label = str(rate_info.get("label", "Roofing"))

    # --- Total with minimum floor ---
    computed_total = round(roof_area_m2 * rate_eur_per_m2, 2)
    minimum = float(rules.get("minimum_total_eur", 800.00))
    minimum_applied = computed_total < minimum
    total_eur = max(computed_total, minimum)

    # --- Human-readable summary ---
    if minimum_applied:
        summary = (
            f"Roofing estimate: {roof_area_m2:.0f} m\u00b2 {roof_type} roof"
            f" — minimum charge applied"
            f" — total \u20ac{total_eur:.2f}"
        )
    else:
        summary = (
            f"Roofing estimate: {roof_area_m2:.0f} m\u00b2 {roof_type} roof"
            f" at \u20ac{rate_eur_per_m2:.2f}/m\u00b2"
            f" — total \u20ac{total_eur:.2f}"
        )

    # --- Rendered plain-text quote block ---
    currency = rules.get("currency", "EUR")
    divider = "-" * 40
    note_line = (
        "\nNote: area not provided — price based on estimated measurement."
        if not area_from_intake else ""
    )
    rendered_text = (
        f"ROOFING ESTIMATE\n"
        f"{divider}\n"
        f"{summary}\n"
        f"{divider}\n"
        f"\n"
        f"  {label}\n"
        f"  {roof_area_m2:.0f} m\u00b2 \u00d7 \u20ac{rate_eur_per_m2:.2f}/m\u00b2"
        f"  =  \u20ac{total_eur:.2f}"
        + (f"\n  (minimum charge applied)" if minimum_applied else "")
        + f"\n"
        f"\n"
        f"{divider}\n"
        f"TOTAL  \u20ac{total_eur:.2f} {currency}"
        + note_line
    )

    lead_id = str(getattr(lead, "id", ""))
    estimate = {
        "workflow": "roofing",
        "lead_id": lead_id,
        "currency": currency,
        "summary": summary,
        "rendered_text": rendered_text,
        "total_eur": total_eur,
        "totals": {"pre_tax": total_eur, "grand_total": total_eur},
        "line_items": [
            {
                "code": "roofing_labor_materials",
                "label": label,
                "quantity": roof_area_m2,
                "unit": "m2",
                "unit_price": rate_eur_per_m2,
                "total": total_eur,
                "category": "labor_materials",
            }
        ],
        "meta": {
            "estimate_id": f"roof_{lead_id}",
            "roof_area_m2": roof_area_m2,
            "roof_type": roof_type,
            "rate_per_m2": rate_eur_per_m2,
            "area_from_intake": area_from_intake,
            "minimum_applied": minimum_applied,
        },
    }
    return StepResult(status="OK", data={"estimate_json": estimate})


step_estimate_v1.__step_contract__ = StepContract(
    produces=["estimate_json"],
    version="1.0",
)


def step_review_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    # Read estimate meta produced by the previous step.
    # The runner stores result.data (a plain dict) in state.data["steps"][step_id],
    # not the StepResult object itself.
    steps = (state.data.get("steps") or {}) if isinstance(state.data, dict) else {}
    estimate_data: Dict[str, Any] = steps.get("estimate") or {}
    meta: Dict[str, Any] = (estimate_data.get("estimate_json") or {}).get("meta") or {}

    review_reasons: list[str] = []

    # Flag: area was not provided by the customer — price is based on a fallback value.
    if not meta.get("area_from_intake", True):
        review_reasons.append("roof_area_missing_from_intake")

    needs_review = len(review_reasons) > 0
    return StepResult(
        status="OK",
        data={"needs_review": needs_review, "review_reasons": review_reasons},
    )


step_review_v1.__step_contract__ = StepContract(
    produces=["needs_review", "review_reasons"],
    version="1.0",
)


def step_store_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    lead: Any = assets["lead"]
    html_key = f"roofing/{getattr(lead, 'id', 'x')}/estimate.html"
    return StepResult(status="OK", data={"estimate_html_key": html_key})


step_store_v1.__step_contract__ = StepContract(
    produces=["estimate_html_key"],
    version="1.0",
)


# ---------------------------------------------------------------------------
# Vertical wiring
# ---------------------------------------------------------------------------

def register_roofing_steps(registry: StepRegistry) -> None:
    registry.register("roofing.estimate.v1", step_estimate_v1)
    registry.register("roofing.review.v1", step_review_v1)
    registry.register("roofing.store.v1", step_store_v1)


def prepare_roofing_assets(db: Session, lead: Any) -> Dict[str, Any]:
    # No vertical-specific precompute needed for skeleton.
    return {}


ROOFING_VERTICAL = VerticalDefinition(
    vertical_id="roofing",
    register_steps_fn=register_roofing_steps,
    prepare_assets_fn=prepare_roofing_assets,
    output_step_id="estimate",
    store_html_step_id="store",
    needs_review_step_id="review",
    pricing_step_id="estimate",
)
