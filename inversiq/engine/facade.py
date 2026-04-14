from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from inversiq.engine.assets import load_assets, repo_root
from inversiq.engine.context import EngineContext
from inversiq.engine.config import load_engine_config
from inversiq.engine.registry import StepRegistry
from inversiq.engine.runner import run_pipeline


class EngineLeadInput(TypedDict, total=False):
    """
    Explicit input contract for the engine facade.

    Documents the Lead fields the engine actually reads.  The facade currently
    accepts a full Lead ORM object (see compute_quote_for_lead_v15 signature),
    but only these fields are consumed anywhere in the engine pipeline.

    Required fields (engine will raise or produce corrupt output without them):
      id          — used in DB queries, S3 path construction, logging
      tenant_id   — used in DB queries, S3 storage prefix, EngineContext

    Optional fields (engine reads with getattr / fallback to None safely):
      intake_payload  — JSON string; parsed for area, customer data, manual_override flag
      square_meters   — numeric area fallback when not present in intake_payload
      name            — customer name (output and review steps)
      email           — customer email (output step)
      phone           — customer phone (output step)

    Not read by the engine (even though present on Lead ORM):
      status, estimate_json, estimate_html_key, vertical, created_at, updated_at,
      and any ORM relationships (tenant, files).

    Note: the engine steps also issue their own DB queries for related data
    (Tenant, User, LeadFile, UploadRecord) rather than relying on pre-loaded
    ORM associations.  This means the engine does not need an eager-loaded Lead.

    Migration path: engine steps in paintly_steps.py still import app.models directly
    (Lead, Tenant, User, etc.) for DB queries.  Once those are refactored to receive
    plain data rather than ORM objects, the engine package will have no app.models
    dependency at all.
    """

    # Required
    id: str
    tenant_id: str

    # Optional
    intake_payload: Optional[str]
    square_meters: Optional[float]
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]


class EngineQuoteResult(TypedDict):
    """
    Explicit contract for the value returned by compute_quote_for_lead_v15.

    Load-bearing keys (callers may depend on these):
      estimate_json       — the estimate payload; always dict | None (normalized by facade);
                            None only on engine step wiring bug or missing output step
      estimate_html_key   — S3 path for the rendered HTML; always a non-empty str
                            (facade raises RuntimeError if this would be falsy)
      needs_review        — routing decision; True → Lead.status = NEEDS_REVIEW

    Diagnostic keys (present for observability/ML capture; callers should not gate logic on these):
      engine_status       — raw pipeline status string ("SUCCEEDED" | "NEEDS_REVIEW")
      trace_id            — unique trace identifier for this run
      debug_pricing_raw   — inner pricing step payload; None if pricing step absent
      available_steps     — step names present in the pipeline state (debug only)
      logs_tail           — last 25 pipeline log entries (debug only)
    """

    # Load-bearing
    estimate_json: Optional[Dict[str, Any]]   # normalized: dict if engine produced output, else None
    estimate_html_key: str                    # non-empty; facade raises before returning if falsy
    needs_review: bool

    # Diagnostic
    engine_status: str
    trace_id: str
    debug_pricing_raw: Optional[Dict[str, Any]]
    available_steps: List[str]
    logs_tail: List[Dict[str, Any]]


def _normalize_estimate(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize the estimate_json value coming out of the output step.

    The pipeline step may store estimate_json as:
      - dict  : already parsed (most common path)
      - str   : serialized by a step before returning (serialization artifact)
      - other : None, or an unexpected type (step wiring bug)

    This function guarantees the facade always returns dict | None.

    Edge case: an invalid (non-parseable) JSON string normalizes to None rather
    than being passed through as a corrupt string.  This is intentional — a
    corrupt string is not a valid estimate and None is the safer sentinel.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None



def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _tail(xs: list, n: int = 50) -> list:
    return xs[-n:] if xs else []


def _step_payload(step: Any) -> Dict[str, Any]:
    """
    Steps in state.data["steps"] are usually StepResult objects:
      StepResult(status=..., data={...}, ...)
    but sometimes they may already be plain dicts.
    This helper always returns the underlying payload dict.
    """
    if step is None:
        return {}
    if isinstance(step, dict):
        # Sometimes serialized StepResult: {"status": "...", "data": {...}}
        if isinstance(step.get("data"), dict):
            return step.get("data") or {}
        return step
    data = getattr(step, "data", None)
    if isinstance(data, dict):
        return data
    # Pydantic models etc.
    if hasattr(step, "model_dump"):
        try:
            d = step.model_dump()
            if isinstance(d, dict) and isinstance(d.get("data"), dict):
                return d["data"]
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    if hasattr(step, "dict"):
        try:
            d = step.dict()
            if isinstance(d, dict) and isinstance(d.get("data"), dict):
                return d["data"]
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_pricing_raw(
    steps: Dict[str, Any], step_id: str = "pricing"
) -> Optional[Dict[str, Any]]:
    """
    Returns the inner pricing dict from the named step's payload.
    Step payload shape: {"pricing": {...actual pricing dict...}}
    step_id defaults to "pricing" (painting convention); pass vertical.pricing_step_id to override.
    """
    pricing_step = steps.get(step_id) if isinstance(steps, dict) else None
    payload = _step_payload(pricing_step)
    if not payload:
        return None

    inner = payload.get("pricing")
    if isinstance(inner, dict):
        return inner

    return payload if isinstance(payload, dict) else None


def _as_decimal_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    try:
        d = Decimal(str(x))
        # normalize to 2dp string
        return f"{d:.2f}"
    except Exception:
        return None


def _apply_option1_provisional_total_if_missing(
    estimate: Any,
    pricing_raw: Optional[Dict[str, Any]],
    *,
    minimum_total_usd: str = "500.00",  # ✅ MVP safety net; adjust to taste
) -> tuple[Any, bool]:
    """
    Option 1:
    If estimate totals are missing/zero BUT pricing_raw has estimate_range,
    set totals to high_usd (else low_usd) and add a provisional line_item.

    If estimate_range exists but is 0.0 (your current case), use minimum_total_usd
    so customer never sees $0.00.
    """
    if not isinstance(estimate, dict):
        return estimate, False
    if not isinstance(pricing_raw, dict):
        return estimate, False

    er = pricing_raw.get("estimate_range")
    if not isinstance(er, dict):
        return estimate, False

    chosen = er.get("high_usd") or er.get("low_usd")
    chosen_str = _as_decimal_str(chosen)

    # If estimate_range resolves to 0.00 (your current case), apply MVP minimum.
    if not chosen_str or chosen_str == "0.00":
        chosen_str = minimum_total_usd

    totals = estimate.get("totals") or {}
    if not isinstance(totals, dict):
        totals = {}

    gt = totals.get("grand_total")
    gt_str = _as_decimal_str(gt)

    # missing if None or "0.00"
    missing = (gt is None) or (gt_str is None) or (gt_str == "0.00")
    if not missing:
        return estimate, False

    # set totals
    totals["pre_tax"] = chosen_str
    totals["grand_total"] = chosen_str
    estimate["totals"] = totals

    # ensure at least one line item
    lis = estimate.get("line_items")
    if not isinstance(lis, list) or len(lis) == 0:
        estimate["line_items"] = [
            {
                "code": "provisional_estimate",
                "label": "Provisional estimate",
                "description": "Provisional estimate (Option 1). Final price after quick review.",
                "quantity": 1,
                "unit": "job",
                "unit_price": chosen_str,
                "total": chosen_str,
                "category": "labor",
                "assumptions": {},
            }
        ]

    # update meta reasons
    meta = estimate.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    reasons = meta.get("needs_review_reasons") or []
    if not isinstance(reasons, list):
        reasons = []

    # remove missing_total, add provisional_total
    reasons = [r for r in reasons if r != "missing_total"]
    if "provisional_total" not in reasons:
        reasons.append("provisional_total")

    meta["needs_review_reasons"] = reasons
    estimate["meta"] = meta

    return estimate, True


# ---------------------------------------------------------------------------
# Engine validation note — 2025
#
# Proven: three workflows (painting, roofing, solar) ran end-to-end through
# compute_quote_for_lead_v15 without changes to the engine core.
# VerticalDefinition correctly routes config load, step registration, asset
# preparation, and result extraction per workflow.
#
# Phase-1 conventions (acceptable, intentional, not bugs):
#   - engine_config/{vertical_id}.json must exist with "assets.rules" and
#     "assets.template" keys, even if the workflow has no render step.
#   - The output step must return data["estimate_json"].
#   - The store step must return a non-empty data["estimate_html_key"].
#     Non-HTML workflows can return a synthetic key (e.g. a path or URI).
#   - data["needs_review"] bool is the canonical review signal.
#
# Remaining painting-specific leakage in the generic path:
#   - _apply_option1_provisional_total_if_missing: painting-specific fallback
#     logic that runs for all verticals; silently no-ops unless the pricing step
#     returns an estimate_range dict.  Label fixed to generic wording (see below).
#     Should eventually move to a VerticalDefinition post-processing hook.
# ---------------------------------------------------------------------------


@dataclass
class VerticalDefinition:
    """
    All caller-supplied hooks and configuration for one workflow vertical.

    Required:
      vertical_id         — key for engine_config/{vertical_id}.json
      register_steps_fn   — registers the vertical's step implementations into a StepRegistry
      prepare_assets_fn   — returns vertical-specific extra assets merged into the base assets dict

    Result-extraction step IDs (defaults match the current painting pipeline):
      output_step_id       — step whose data["estimate_json"] becomes the output estimate
      store_html_step_id   — step whose data["estimate_html_key"] becomes the HTML location
      needs_review_step_id — step whose data["needs_review"] becomes the review flag
      pricing_step_id      — step used for the provisional-total debug pass (painting-specific
                             logic; silently no-ops for verticals without a matching step)

    A second vertical (e.g. solar) only needs to override the fields that differ.
    Painting inherits all defaults unchanged.
    """

    vertical_id: str
    register_steps_fn: Callable[[StepRegistry], None]
    prepare_assets_fn: Callable[[Session, Any], Dict[str, Any]]
    # Result extraction — defaults match painting pipeline step IDs
    output_step_id: str = "output"
    store_html_step_id: str = "store_html"
    needs_review_step_id: str = "needs_review"
    pricing_step_id: str = "pricing"


def compute_quote_for_lead_v15(
    db: Session,
    lead: EngineLeadInput,  # at runtime a Lead ORM instance; see EngineLeadInput for consumed fields
    vertical: VerticalDefinition,
) -> EngineQuoteResult:
    root = repo_root()

    # 1) load engine config
    cfg_path = root / "engine_config" / f"{vertical.vertical_id}.json"
    cfg = load_engine_config(_load_json(cfg_path))

    # 2) registry — populated by the vertical's register_steps_fn
    registry = StepRegistry()
    vertical.register_steps_fn(registry)

    # 3) context
    ctx = EngineContext(
        tenant_id=str(lead.tenant_id),
        vertical_id=vertical.vertical_id,
        lead_id=str(lead.id),
    )

    # 4) rules
    rules_dict: Dict[str, Any] = {}
    if cfg.rules_path:
        rp = root / cfg.rules_path
        if rp.exists():
            rules_dict = _load_json(rp)

    # 5) assets (template + jinja env)
    assets_obj = load_assets(cfg, rules=rules_dict)

    # 6) vertical-specific asset preparation (painting: tenant_pricing, image_refs, branding_context)
    _extra_assets = vertical.prepare_assets_fn(db, lead)

    assets = {
        "db": db,
        "lead": lead,
        "rules": rules_dict,
        "jinja_env": assets_obj.jinja_env,
        "template_path": assets_obj.template_path,
        **_extra_assets,
    }

    # 6) run pipeline — pass db so PipelineRun rows are persisted for every invocation;
    #    this is also the prerequisite for the idempotency guard in publish_quote.
    state = run_pipeline(
        context=ctx,
        config=cfg,
        registry=registry,
        assets=assets,
        initial_data={},
        db=db,
    )

    logs = getattr(state, "logs", []) or []
    failure_step = getattr(state, "failure_step", None)

    steps = (state.data.get("steps") or {}) if isinstance(state.data, dict) else {}
    available_steps = list(steps.keys()) if isinstance(steps, dict) else []

    # ✅ Only raise on FAILED. NEEDS_REVIEW is a valid outcome.
    if state.status == "FAILED":
        error_summary = None
        for entry in reversed(logs):
            if (
                isinstance(entry, dict)
                and entry.get("message") == "step_end"
                and entry.get("step_id") == failure_step
                and entry.get("error")
            ):
                error_summary = entry.get("error")
                break

        raise RuntimeError(
            "engine_pipeline_failed:"
            f"(status={state.status}, "
            f"failure_step={failure_step}, "
            f"error={error_summary}, "
            f"available_steps={available_steps}, "
            f"logs_tail={_tail(logs, 25)})"
        )

    # ✅ Success OR needs-review: return best-effort outputs
    output_step = _step_payload(steps.get(vertical.output_step_id))
    store_step = _step_payload(steps.get(vertical.store_html_step_id))
    nr_step = _step_payload(steps.get(vertical.needs_review_step_id))

    estimate = _normalize_estimate(output_step.get("estimate_json"))
    html_key = store_step.get("estimate_html_key")

    # needs_review bool: prefer step output, else infer from state.status
    needs_review = bool(nr_step.get("needs_review", state.status == "NEEDS_REVIEW"))

    # ---- Debug-friendly extras + raw pricing payload ----
    pricing_raw = _extract_pricing_raw(steps, step_id=vertical.pricing_step_id)

    # ---- Option 1: force provisional totals if missing_total but we have estimate_range ----
    estimate, forced_needs_review = _apply_option1_provisional_total_if_missing(
        estimate,
        pricing_raw,
        minimum_total_usd="500.00",  # <-- change if you want
    )
    if forced_needs_review:
        needs_review = True

        # Keep review reasons as diagnostic metadata only.
        # Do NOT force needs_review just because reasons are present.
    #  try:
    #    if isinstance(estimate, dict):
    #      meta = estimate.get("meta") or {}
    #    reasons = meta.get("needs_review_reasons") or []
    #  if not isinstance(reasons, list):
    #    reasons = []
    # except Exception:
    #   pass

    # If HTML wasn't stored, that's an actual engine wiring bug
    if not html_key:
        raise RuntimeError(
            "engine_missing_estimate_html_key:"
            f"(status={state.status}, available_steps={available_steps}, logs_tail={_tail(logs, 25)})"
        )

    return {
        "estimate_json": estimate,
        "estimate_html_key": html_key,
        "needs_review": needs_review,
        "engine_status": state.status,
        "trace_id": ctx.trace_id,
        # ✅ expose for adapter debug
        "available_steps": available_steps,
        "logs_tail": _tail(logs, 25),
        "debug_pricing_raw": pricing_raw,
    }
