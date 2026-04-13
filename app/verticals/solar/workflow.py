"""
app/verticals/solar/workflow.py

Solar workflow — kWp-based pricing.

Pricing logic (step_quote_v1):
  - Reads system_kw from lead.intake_payload (JSON string).
  - Falls back to rules["default_system_kw"], then 5.0 kWp.
  - Multiplies by rules["rate_eur_per_kw"] (default €1,500/kWp).
  - Applies minimum_total_eur floor from rules.
  - Records kw_from_intake in meta (True only when intake had system_kw).

Review logic (step_review_v1):
  - Marks needs_review=True when kw_from_intake is False.
  - Rationale: a fallback system size means the price is based on a default,
    not a customer-supplied specification. A human should confirm before sending.
  - Populates review_reasons list for downstream use.

Uses deliberately different step IDs ("quote", "save") vs painting ("output", "store_html")
to verify the facade routes correctly via VerticalDefinition.

Steps:
  solar.quote.v1   — kWp-based pricing from intake_payload + rules
  solar.review.v1  — flags review when system_kw was not in intake
  solar.save.v1    — returns a fake storage key
"""
from __future__ import annotations

import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from inversiq.engine.config import StepConfig
from inversiq.engine.context import PipelineState, StepResult
from inversiq.engine.facade import VerticalDefinition
from inversiq.engine.registry import StepRegistry


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_quote_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
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

    # --- System size: intake > rules default > 5.0 kWp ---
    # kw_from_intake is True only when the customer explicitly provided system_kw.
    kw_from_intake: bool = intake.get("system_kw") is not None
    system_kw = 5.0
    try:
        v = intake.get("system_kw")
        if v is not None:
            system_kw = float(v)
        elif rules.get("default_system_kw"):
            system_kw = float(rules["default_system_kw"])
    except Exception:
        pass

    # --- Rate lookup ---
    rate_eur_per_kw = float(rules.get("rate_eur_per_kw", 1500.00))

    # --- Total with minimum floor ---
    computed_total = round(system_kw * rate_eur_per_kw, 2)
    minimum = float(rules.get("minimum_total_eur", 3000.00))
    minimum_applied = computed_total < minimum
    total_eur = max(computed_total, minimum)

    # --- Human-readable summary ---
    currency = rules.get("currency", "EUR")
    if minimum_applied:
        summary = (
            f"Solar estimate: {system_kw:.1f} kWp system"
            f" \u2014 minimum charge applied"
            f" \u2014 total \u20ac{total_eur:.2f}"
        )
    else:
        summary = (
            f"Solar estimate: {system_kw:.1f} kWp system"
            f" at \u20ac{rate_eur_per_kw:.2f}/kWp"
            f" \u2014 total \u20ac{total_eur:.2f}"
        )

    # --- Rendered plain-text quote block ---
    line_label = f"Solar panel installation ({system_kw:.1f} kWp)"
    divider = "-" * 40
    note_line = (
        "\nNote: system size not provided \u2014 price based on default estimate."
        if not kw_from_intake else ""
    )
    rendered_text = (
        f"SOLAR ESTIMATE\n"
        f"{divider}\n"
        f"{summary}\n"
        f"{divider}\n"
        f"\n"
        f"  {line_label}\n"
        f"  {system_kw:.1f} kWp \u00d7 \u20ac{rate_eur_per_kw:.2f}/kWp"
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
        "workflow": "solar",
        "lead_id": lead_id,
        "currency": currency,
        "summary": summary,
        "rendered_text": rendered_text,
        "system_kw": system_kw,
        "total_eur": total_eur,
        "totals": {"pre_tax": total_eur, "grand_total": total_eur},
        "line_items": [
            {
                "code": "solar_installation",
                "label": f"Solar panel installation ({system_kw:.1f} kWp)",
                "quantity": system_kw,
                "unit": "kWp",
                "unit_price": rate_eur_per_kw,
                "total": total_eur,
                "category": "installation",
            }
        ],
        "meta": {
            "estimate_id": f"solar_{lead_id}",
            "system_kw": system_kw,
            "rate_per_kw": rate_eur_per_kw,
            "kw_from_intake": kw_from_intake,
            "minimum_applied": minimum_applied,
        },
    }
    return StepResult(status="OK", data={"estimate_json": estimate})


def step_review_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    # The runner stores result.data (a plain dict) in state.data["steps"][step_id].
    steps = (state.data.get("steps") or {}) if isinstance(state.data, dict) else {}
    quote_data: Dict[str, Any] = steps.get("quote") or {}
    meta: Dict[str, Any] = (quote_data.get("estimate_json") or {}).get("meta") or {}

    review_reasons: list[str] = []

    # Flag: system size not provided by the customer — price is based on a default.
    if not meta.get("kw_from_intake", True):
        review_reasons.append("system_kw_missing_from_intake")

    needs_review = len(review_reasons) > 0
    return StepResult(
        status="OK",
        data={"needs_review": needs_review, "review_reasons": review_reasons},
    )


def step_save_v1(state: PipelineState, step: StepConfig, assets: dict) -> StepResult:
    lead: Any = assets["lead"]
    html_key = f"solar/{getattr(lead, 'id', 'x')}/quote.html"
    return StepResult(status="OK", data={"estimate_html_key": html_key})


# ---------------------------------------------------------------------------
# Vertical wiring
# ---------------------------------------------------------------------------

def register_solar_steps(registry: StepRegistry) -> None:
    registry.register("solar.quote.v1", step_quote_v1)
    registry.register("solar.review.v1", step_review_v1)
    registry.register("solar.save.v1", step_save_v1)


def prepare_solar_assets(db: Session, lead: Any) -> Dict[str, Any]:
    # No vertical-specific precompute needed yet.
    return {}


SOLAR_VERTICAL = VerticalDefinition(
    vertical_id="solar",
    register_steps_fn=register_solar_steps,
    prepare_assets_fn=prepare_solar_assets,
    output_step_id="quote",
    store_html_step_id="save",
    needs_review_step_id="review",
    pricing_step_id="quote",
)
