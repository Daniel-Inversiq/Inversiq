from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.anomaly.engine import run_all
from app.anomaly.types import AnomalyType
from app.auth.deps import require_user_html
from app.db import get_db
from app.health.summary import pipeline_health_summaries
from app.i18n.service import setup_jinja_i18n
from app.intelligence.engine import run_all as run_intelligence_signals
from app.intelligence.types import SignalType
from app.models.pipeline_run import PipelineRun
from app.models.proposed_change_apply_intent import ProposedChangeApplyIntent
from app.models.proposed_change_execution_attempt import ProposedChangeExecutionAttempt
from app.models.proposed_change_execution_outcome import ProposedChangeExecutionOutcome
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.models.user import User
from app.review_inbox.query import build_inbox_items
from app.routers.focus import get_pipeline_focus, get_vertical_focus
from app.routers.control_suggestions import (
    get_pipeline_control_suggestions,
    get_vertical_control_suggestions,
)
from app.routers.pipeline_runs import build_pipeline_run_debug_payload
from app.routers.reasoning import get_pipeline_reasoning, get_vertical_reasoning
from app.routers.review_state import get_review_state
from app.routers.review_state import ReviewStatePayload, upsert_review_state
from app.routers.simulation_preview import (
    get_pipeline_simulation_previews,
    get_vertical_simulation_previews,
)
from app.routers.proposed_change_actions import (
    ApproveRequest,
    CancelReadyForApplyRequest,
    MarkReadyForApplyRequest,
    RejectRequest,
    ReopenRequest,
    approve as pc_action_approve,
    cancel_ready_for_apply as pc_action_cancel_ready_for_apply,
    mark_ready_for_apply as pc_action_mark_ready_for_apply,
    reject as pc_action_reject,
    reopen as pc_action_reopen,
)
from app.routers.proposed_change_audit import get_proposed_change_audit
from app.routers.proposed_change_state import ProposedChangeStatePayload, upsert_proposed_change_state
from app.routers.proposed_changes import (
    get_pipeline_proposed_changes,
    get_vertical_proposed_changes,
)
from app.routers.proposal_conflicts import (
    get_pipeline_proposal_conflicts,
    get_vertical_proposal_conflicts,
)
from app.routers.proposal_approval_readiness import (
    get_pipeline_approval_readiness,
    get_vertical_approval_readiness,
)
from app.routers.proposal_staleness import (
    get_pipeline_proposal_staleness,
    get_vertical_proposal_staleness,
)
from app.routers.proposal_apply_planning import (
    get_pipeline_apply_planning,
    get_vertical_apply_planning,
)
from app.routers.proposed_change_apply_intents import _to_dict as _apply_intent_to_dict
from app.routers.proposed_change_execution_outcomes import _outcome_to_dict
from app.routers.proposed_change_execution_attempts import _attempt_to_dict
from app.routers.proposed_change_execution_requests import _to_dict as _execution_request_to_dict

router = APIRouter(prefix="/ops", tags=["ops"])
templates = Jinja2Templates(directory="app/templates")
setup_jinja_i18n(templates)

_CONTROL_SUGGESTION_CATEGORY_OPTIONS = [
    "confidence_threshold_tuning",
    "review_trigger_narrowing",
    "validation_step_tightening",
    "fallback_path_hardening",
    "margin_guardrail_adjustment",
    "no_safe_adjustment",
]

_PROPOSED_CHANGE_TYPE_OPTIONS = [
    "threshold_adjustment",
    "review_trigger_adjustment",
    "validation_policy_adjustment",
    "fallback_policy_adjustment",
    "pricing_guardrail_adjustment",
    "no_action_proposed",
]

_RISK_LEVEL_FILTER_OPTIONS = ["low", "medium", "high"]

_STALENESS_STATUS_FILTER_OPTIONS = ["all", "fresh", "aging", "stale", "superseded"]

_READINESS_STATUS_FILTER_OPTIONS = [
    "all",
    "approval_ready",
    "blocked_with_warnings",
    "blocked",
]

_PLANNING_STATUS_FILTER_OPTIONS = [
    "all",
    "planned",
    "blocked_from_planning",
    "requires_combined_plan",
]

_APPLY_INTENT_STATUS_FILTER_OPTIONS = ["all", "ready_for_apply", "cancelled"]

_EXECUTION_REQUEST_STATUS_FILTER_OPTIONS = [
    "all",
    "requested",
    "validated",
    "blocked",
    "cancelled",
]

_EXECUTION_REQUEST_SCOPE_TYPE_FILTER_OPTIONS = ["all", "vertical", "pipeline"]

_EXECUTION_OUTCOME_STATUS_FILTER_OPTIONS = ["all", "success", "partial", "failed"]

_EXECUTION_EVALUATION_STATUS_FILTER_OPTIONS = [
    "all",
    "improved",
    "neutral",
    "degraded",
    "unstable",
]

_EXECUTION_ATTEMPT_STATUS_FILTER_OPTIONS = [
    "all",
    "queued",
    "running",
    "succeeded",
    "failed",
    "rolled_back",
    "cancelled",
]


def _prepare_apply_intent_for_template(d: dict[str, Any]) -> dict[str, Any]:
    """Add JSON strings and display fields for ops templates."""
    out = dict(d)
    for key in (
        "governance_snapshot",
        "proposal_payload",
        "apply_plan_snapshot",
        "preflight_snapshot",
        "rollback_snapshot",
    ):
        v = out.get(key)
        out[f"{key}_json"] = (
            json.dumps(v, indent=2, default=str) if v is not None else ""
        )
    for dk in ("created_at", "updated_at"):
        v = out.get(dk)
        if v is not None and hasattr(v, "isoformat"):
            out[f"{dk}_display"] = v.isoformat()
        else:
            out[f"{dk}_display"] = str(v) if v is not None else "—"
    st = (out.get("scope_type") or "").strip().lower()
    sid = out.get("scope_id") or ""
    if st == "vertical":
        out["scope_ui_label"] = f"vertical · {sid}"
    elif st == "pipeline":
        out["scope_ui_label"] = f"pipeline · {sid}"
    else:
        out["scope_ui_label"] = f"{st or '—'} · {sid}" if st else (sid or "—")
    st_l = (out.get("scope_type") or "").strip().lower()
    out["proposed_changes_scope_param"] = (
        "verticals" if st_l == "vertical" else "pipelines"
    )
    return out


def _load_apply_intent_map(db: Session, tenant_id: Optional[str]) -> dict[str, dict[str, Any]]:
    """change_id → apply intent dict (with snapshots), same shape as GET API with include_snapshots=True."""
    tid = (tenant_id or "").strip()
    if not tid:
        return {}
    rows = (
        db.query(ProposedChangeApplyIntent)
        .filter(ProposedChangeApplyIntent.tenant_id == tid)
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw = _apply_intent_to_dict(row, include_snapshots=True)
        cid = (raw.get("change_id") or "").strip()
        if cid:
            out[cid] = _prepare_apply_intent_for_template(raw)
    return out


def _prepare_execution_request_for_template(d: dict[str, Any]) -> dict[str, Any]:
    """Add JSON strings and display fields for ops templates (GET API shape with snapshots)."""
    out = dict(d)
    for key in (
        "governance_snapshot",
        "execution_plan_snapshot",
        "preflight_snapshot",
        "monitoring_plan_snapshot",
        "blocking_reasons_snapshot",
        "apply_intent_snapshot",
        "proposal_payload",
    ):
        v = out.get(key)
        out[f"{key}_json"] = (
            json.dumps(v, indent=2, default=str) if v is not None else ""
        )
    for dk in ("created_at", "updated_at"):
        v = out.get(dk)
        if v is not None and hasattr(v, "isoformat"):
            out[f"{dk}_display"] = v.isoformat()
        else:
            out[f"{dk}_display"] = str(v) if v is not None else "—"
    st = (out.get("scope_type") or "").strip().lower()
    sid = out.get("scope_id") or ""
    if st == "vertical":
        out["scope_ui_label"] = f"vertical · {sid}"
    elif st == "pipeline":
        out["scope_ui_label"] = f"pipeline · {sid}"
    else:
        out["scope_ui_label"] = f"{st or '—'} · {sid}" if st else (sid or "—")
    st_l = (out.get("scope_type") or "").strip().lower()
    out["proposed_changes_scope_param"] = (
        "verticals" if st_l == "vertical" else "pipelines"
    )
    return out


def _load_execution_request_map(db: Session, tenant_id: Optional[str]) -> dict[str, dict[str, Any]]:
    """change_id → execution request dict (with snapshots), same as GET /api/.../execution-requests/{id}."""
    tid = (tenant_id or "").strip()
    if not tid:
        return {}
    rows = (
        db.query(ProposedChangeExecutionRequest)
        .filter(ProposedChangeExecutionRequest.tenant_id == tid)
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw = _execution_request_to_dict(row, include_snapshots=True)
        cid = (raw.get("change_id") or "").strip()
        if cid:
            out[cid] = _prepare_execution_request_for_template(raw)
    return out


def _prepare_execution_outcome_for_template(d: dict[str, Any]) -> dict[str, Any]:
    """JSON strings and display fields for ops templates (GET /api/proposed-change-execution-outcomes shape)."""
    out = dict(d)
    for key in (
        "observed_metrics_snapshot",
        "expected_metrics_snapshot",
        "deviation_snapshot",
    ):
        v = out.get(key)
        out[f"{key}_json"] = (
            json.dumps(v, indent=2, default=str) if v is not None else ""
        )
    for dk in ("created_at", "updated_at"):
        v = out.get(dk)
        if v is not None and hasattr(v, "isoformat"):
            out[f"{dk}_display"] = v.isoformat()
        else:
            out[f"{dk}_display"] = str(v) if v is not None else "—"
    st = (out.get("scope_type") or "").strip().lower()
    sid = out.get("scope_id") or ""
    if st == "vertical":
        out["scope_ui_label"] = f"vertical · {sid}"
    elif st == "pipeline":
        out["scope_ui_label"] = f"pipeline · {sid}"
    else:
        out["scope_ui_label"] = f"{st or '—'} · {sid}" if st else (sid or "—")
    st_l = (out.get("scope_type") or "").strip().lower()
    out["proposed_changes_scope_param"] = (
        "verticals" if st_l == "vertical" else "pipelines"
    )
    return out


def _load_execution_outcome_map(db: Session, tenant_id: Optional[str]) -> dict[str, dict[str, Any]]:
    """change_id → outcome dict (newest first per change_id), same records as GET /api/.../execution-outcomes."""
    tid = (tenant_id or "").strip()
    if not tid:
        return {}
    rows = (
        db.query(ProposedChangeExecutionOutcome)
        .filter(ProposedChangeExecutionOutcome.tenant_id == tid)
        .order_by(ProposedChangeExecutionOutcome.created_at.desc())
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw = _outcome_to_dict(row)
        cid = (raw.get("change_id") or "").strip()
        if cid and cid not in out:
            out[cid] = _prepare_execution_outcome_for_template(raw)
    return out


def _prepare_execution_attempt_for_template(d: dict[str, Any]) -> dict[str, Any]:
    """JSON strings and display fields for ops templates (GET /api/proposed-change-execution-attempts shape)."""
    out = dict(d)
    for key in (
        "preflight_result_snapshot",
        "execution_result_snapshot",
        "rollback_snapshot",
    ):
        v = out.get(key)
        out[f"{key}_json"] = (
            json.dumps(v, indent=2, default=str) if v is not None else ""
        )
    for dk in ("created_at", "updated_at", "started_at", "completed_at"):
        v = out.get(dk)
        if v is not None and hasattr(v, "isoformat"):
            out[f"{dk}_display"] = v.isoformat()
        else:
            out[f"{dk}_display"] = str(v) if v is not None else "—"
    return out


def _load_execution_attempts_map(
    db: Session, tenant_id: Optional[str]
) -> dict[str, list[dict[str, Any]]]:
    """change_id → execution attempt rows (newest first), same as GET /api/.../execution-attempts."""
    tid = (tenant_id or "").strip()
    if not tid:
        return {}
    rows = (
        db.query(ProposedChangeExecutionAttempt)
        .filter(ProposedChangeExecutionAttempt.tenant_id == tid)
        .order_by(
            ProposedChangeExecutionAttempt.created_at.desc(),
            ProposedChangeExecutionAttempt.attempt_number.desc(),
        )
        .all()
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        raw = _attempt_to_dict(row, include_snapshots=True)
        cid = (raw.get("change_id") or "").strip()
        if not cid:
            continue
        out.setdefault(cid, []).append(_prepare_execution_attempt_for_template(raw))
    return out


def _query_execution_attempts_for_ops_list(
    db: Session,
    *,
    tenant_id: str,
    status: Optional[str],
) -> list[dict[str, Any]]:
    """Rows for ops execution-attempts table, same records as GET /api/proposed-change-execution-attempts."""
    q = db.query(ProposedChangeExecutionAttempt).filter(
        ProposedChangeExecutionAttempt.tenant_id == tenant_id
    )
    st = (status or "").strip().lower()
    if st and st != "all":
        q = q.filter(ProposedChangeExecutionAttempt.status == st)
    rows = (
        q.order_by(
            ProposedChangeExecutionAttempt.created_at.desc(),
            ProposedChangeExecutionAttempt.attempt_number.desc(),
        )
        .limit(500)
        .all()
    )
    return [_prepare_execution_attempt_for_template(_attempt_to_dict(r)) for r in rows]


def _query_execution_outcomes_for_ops_list(
    db: Session,
    *,
    tenant_id: str,
    outcome_status: Optional[str],
    evaluation_status: Optional[str],
) -> list[dict[str, Any]]:
    """Rows for ops execution-outcomes table (same filters as GET /api/proposed-change-execution-outcomes)."""
    q = db.query(ProposedChangeExecutionOutcome).filter(
        ProposedChangeExecutionOutcome.tenant_id == tenant_id
    )
    os_ = (outcome_status or "").strip().lower()
    if os_ and os_ != "all":
        q = q.filter(ProposedChangeExecutionOutcome.outcome_status == os_)
    es = (evaluation_status or "").strip().lower()
    if es and es != "all":
        q = q.filter(ProposedChangeExecutionOutcome.evaluation_status == es)

    rows = (
        q.order_by(ProposedChangeExecutionOutcome.created_at.desc()).limit(500).all()
    )
    return [_prepare_execution_outcome_for_template(_outcome_to_dict(r)) for r in rows]


def _query_execution_requests_for_ops_list(
    db: Session,
    *,
    tenant_id: str,
    status: Optional[str],
    scope_type: Optional[str],
    scope_id: Optional[str],
) -> list[dict[str, Any]]:
    """Rows for ops execution-requests table, same records as GET /api/proposed-change-execution-requests."""
    q = db.query(ProposedChangeExecutionRequest).filter(
        ProposedChangeExecutionRequest.tenant_id == tenant_id
    )
    st = (status or "").strip().lower()
    if st and st != "all":
        q = q.filter(ProposedChangeExecutionRequest.status == st)

    rows = q.order_by(ProposedChangeExecutionRequest.created_at.desc()).all()
    scope_t = (scope_type or "").strip().lower()
    sid_f = (scope_id or "").strip()
    out: list[dict[str, Any]] = []
    for row in rows:
        raw = _execution_request_to_dict(row, include_snapshots=True)
        prepared = _prepare_execution_request_for_template(raw)
        if scope_t and scope_t != "all":
            if (prepared.get("scope_type") or "").strip().lower() != scope_t:
                continue
        if sid_f and (prepared.get("scope_id") or "").strip() != sid_f:
            continue
        out.append(prepared)
    return out


def _filter_proposed_change_items_by_change_id(
    items: list[dict],
    change_id: str,
) -> list[dict]:
    cid = (change_id or "").strip()
    if not cid:
        return items
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        new_pcs: list[dict] = []
        for c in item.get("proposed_changes") or []:
            if (c.get("change_id") or "").strip() == cid:
                new_pcs.append(c)
        item["proposed_changes"] = new_pcs
        if new_pcs:
            out.append(item)
    return out


def _query_apply_intents_for_ops_list(
    db: Session,
    *,
    tenant_id: str,
    status: Optional[str],
) -> list[dict[str, Any]]:
    q = db.query(ProposedChangeApplyIntent).filter(
        ProposedChangeApplyIntent.tenant_id == tenant_id
    )
    st = (status or "").strip().lower()
    if st and st in ("ready_for_apply", "cancelled"):
        q = q.filter(ProposedChangeApplyIntent.status == st)
    rows = q.order_by(ProposedChangeApplyIntent.created_at.desc()).all()
    return [_prepare_apply_intent_for_template(_apply_intent_to_dict(r, include_snapshots=True)) for r in rows]


@dataclass(frozen=True)
class OpsPCListFilters:
    scope_filter: str
    tenant_id_filter: str
    scope_id_filter: str
    limit_filter: int
    change_type_filter: str
    risk_level_filter: str
    window_days_filter: int
    lookback_days_filter: int
    conflicts_only_filter: str
    staleness_status_filter: str
    readiness_status_filter: str
    planning_status_filter: str
    change_id_filter: str


def get_ops_pc_list_filters(
    scope_filter: Optional[str] = Form(default=""),
    tenant_id_filter: Optional[str] = Form(default=""),
    scope_id_filter: Optional[str] = Form(default=""),
    limit_filter: int = Form(default=50),
    change_type_filter: Optional[str] = Form(default=""),
    risk_level_filter: Optional[str] = Form(default=""),
    window_days_filter: int = Form(default=7),
    lookback_days_filter: int = Form(default=30),
    conflicts_only_filter: Optional[str] = Form(default=""),
    staleness_status_filter: Optional[str] = Form(default=""),
    readiness_status_filter: Optional[str] = Form(default=""),
    planning_status_filter: Optional[str] = Form(default=""),
    change_id_filter: Optional[str] = Form(default=""),
) -> OpsPCListFilters:
    return OpsPCListFilters(
        scope_filter=scope_filter or "",
        tenant_id_filter=tenant_id_filter or "",
        scope_id_filter=scope_id_filter or "",
        limit_filter=limit_filter,
        change_type_filter=change_type_filter or "",
        risk_level_filter=risk_level_filter or "",
        window_days_filter=window_days_filter,
        lookback_days_filter=lookback_days_filter,
        conflicts_only_filter=conflicts_only_filter or "",
        staleness_status_filter=staleness_status_filter or "",
        readiness_status_filter=readiness_status_filter or "",
        planning_status_filter=planning_status_filter or "",
        change_id_filter=change_id_filter or "",
    )


def _ops_pc_list_redirect_url(
    flt: OpsPCListFilters,
    *,
    pc_action_error: Optional[str] = None,
) -> str:
    scope_q = (flt.scope_filter or "").strip().lower()
    if scope_q not in {"pipelines", "verticals"}:
        scope_q = "pipelines"
    query_params: dict[str, str | int] = {
        "scope": scope_q,
        "tenant_id": (flt.tenant_id_filter or "").strip(),
        "scope_id": (flt.scope_id_filter or "").strip(),
        "limit": flt.limit_filter,
        "change_type": (flt.change_type_filter or "").strip(),
        "risk_level": (flt.risk_level_filter or "").strip(),
        "window_days": flt.window_days_filter,
        "lookback_days": flt.lookback_days_filter,
    }
    co = (flt.conflicts_only_filter or "").strip().lower()
    if co in ("1", "yes", "true", "on"):
        query_params["conflicts_only"] = "yes"
    ss = (flt.staleness_status_filter or "").strip().lower()
    if ss and ss in _STALENESS_STATUS_FILTER_OPTIONS and ss != "all":
        query_params["staleness_status"] = ss
    rs = (flt.readiness_status_filter or "").strip().lower()
    if rs and rs in _READINESS_STATUS_FILTER_OPTIONS and rs != "all":
        query_params["readiness_status"] = rs
    ps = (flt.planning_status_filter or "").strip().lower()
    if ps and ps in _PLANNING_STATUS_FILTER_OPTIONS and ps != "all":
        query_params["planning_status"] = ps
    chg = (flt.change_id_filter or "").strip()
    if chg:
        query_params["change_id"] = chg
    if pc_action_error:
        err = pc_action_error.strip()
        if len(err) > 450:
            err = err[:447] + "..."
        query_params["pc_action_error"] = err
    return f"{router.url_path_for('ops_proposed_changes')}?{urlencode(query_params)}"


def _ops_pc_action_error_redirect(flt: OpsPCListFilters, exc: HTTPException) -> RedirectResponse:
    detail = exc.detail
    if isinstance(detail, str):
        msg = detail
    elif isinstance(detail, dict):
        inner = detail.get("detail")
        msg = inner if isinstance(inner, str) else str(detail)
    elif isinstance(detail, list):
        msg = "; ".join(str(x) for x in detail)
    else:
        msg = str(detail)
    msg = (msg or "Action failed").strip()
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt, pc_action_error=msg),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Defaults aligned with GET /api/focus and /api/reasoning. Direct calls to those route
# handlers do not receive FastAPI's Query substitution — bare Query(...) defaults leak
# into timedelta/health code as non-ints and raise TypeError.
_OPS_API_WINDOW_DAYS = 7
_OPS_API_LOOKBACK_DAYS = 30


def _normalize_ops_reasoning_items(items: list[dict]) -> list[dict]:
    """Ensure nested reasoning lists and string lists exist for ops_reasoning.html."""
    out: list[dict] = []
    for raw in items:
        row = dict(raw)
        reasoning_in = row.get("reasoning")
        if not isinstance(reasoning_in, list):
            reasoning_in = []
        reasoning_out: list[dict] = []
        for ri in reasoning_in:
            if not isinstance(ri, dict):
                continue
            ev = ri.get("evidence")
            if ev is None:
                ev_list: list[str] = []
            elif isinstance(ev, list):
                ev_list = [str(x) for x in ev]
            else:
                ev_list = [str(ev)]
            rec = ri.get("recommendations")
            if rec is None:
                rec_list: list[str] = []
            elif isinstance(rec, list):
                rec_list = [str(x) for x in rec]
            else:
                rec_list = [str(rec)]
            reasoning_out.append(
                {
                    "category": (ri.get("category") or "mixed_or_unclear"),
                    "root_cause": ri.get("root_cause") or "",
                    "confidence": ri.get("confidence") or "low",
                    "evidence": ev_list,
                    "recommendations": rec_list,
                }
            )
        row["reasoning"] = reasoning_out
        if row.get("summary") is None:
            row["summary"] = ""
        out.append(row)
    return out


def _filter_control_suggestion_items(
    items: list[dict],
    *,
    category: str,
    scope_id: str,
) -> list[dict]:
    """Apply optional category and scope_id filters (post-load)."""
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        if scope_id and (item.get("scope_id") or "").strip() != scope_id:
            continue
        suggestions = list(item.get("suggestions") or [])
        if category:
            suggestions = [
                s for s in suggestions if (s.get("category") or "").strip().lower() == category
            ]
            if not suggestions:
                continue
        item["suggestions"] = suggestions
        out.append(item)
    return out


def _summarize_control_suggestions(items: list[dict]) -> dict[str, int]:
    total_scopes = len(items)
    scopes_with_suggestions = sum(1 for i in items if len(i.get("suggestions") or []) > 0)
    total_suggestion_rows = sum(len(i.get("suggestions") or []) for i in items)
    scopes_only_no_safe = 0
    for i in items:
        sugs = i.get("suggestions") or []
        if not sugs:
            continue
        if all((s.get("category") or "").strip().lower() == "no_safe_adjustment" for s in sugs):
            scopes_only_no_safe += 1
    return {
        "total_scopes": total_scopes,
        "scopes_with_suggestions": scopes_with_suggestions,
        "total_suggestions": total_suggestion_rows,
        "scopes_only_no_safe": scopes_only_no_safe,
    }


def _filter_simulation_preview_items(
    items: list[dict],
    *,
    category: str,
    scope_id: str,
) -> list[dict]:
    """Apply optional category and scope_id filters (post-load)."""
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        if scope_id and (item.get("scope_id") or "").strip() != scope_id:
            continue
        previews = list(item.get("previews") or [])
        if category:
            previews = [
                p for p in previews if (p.get("category") or "").strip().lower() == category
            ]
            if not previews:
                continue
        item["previews"] = previews
        out.append(item)
    return out


def _summarize_simulation_preview(items: list[dict]) -> dict[str, int]:
    total_scopes = len(items)
    scopes_with_previews = sum(1 for i in items if len(i.get("previews") or []) > 0)
    total_preview_rows = sum(len(i.get("previews") or []) for i in items)
    scopes_weak_only = 0
    for i in items:
        prev = i.get("previews") or []
        if not prev:
            continue
        if all(
            (p.get("confidence") or "").strip().lower() == "low"
            or (p.get("category") or "").strip().lower() == "no_safe_adjustment"
            for p in prev
        ):
            scopes_weak_only += 1
    return {
        "total_scopes": total_scopes,
        "scopes_with_previews": scopes_with_previews,
        "total_previews": total_preview_rows,
        "scopes_weak_only": scopes_weak_only,
    }


def _filter_proposed_change_items(
    items: list[dict],
    *,
    scope_id: str,
    change_type: str,
    risk_level: str,
) -> list[dict]:
    """Apply optional scope_id, change_type, and risk_level filters (post-load)."""
    out: list[dict] = []
    sid = (scope_id or "").strip()
    ct_filter = (change_type or "").strip().lower()
    rl_filter = (risk_level or "").strip().lower()
    for raw in items:
        item = dict(raw)
        if sid and (item.get("scope_id") or "").strip() != sid:
            continue
        changes = list(item.get("proposed_changes") or [])
        filtered: list[dict] = []
        for c in changes:
            ct = (c.get("change_type") or "").strip().lower()
            if ct_filter and ct != ct_filter:
                continue
            ai = c.get("approval_intent") or {}
            rl = str(ai.get("risk_level") or "").strip().lower()
            if rl_filter and rl != rl_filter:
                continue
            filtered.append(c)
        item["proposed_changes"] = filtered
        if ct_filter or rl_filter:
            if not filtered:
                continue
        out.append(item)
    return out


def _summarize_proposed_changes(items: list[dict]) -> dict[str, int]:
    total_scopes = len(items)
    scopes_with_changes = sum(1 for i in items if len(i.get("proposed_changes") or []) > 0)
    total_change_rows = sum(len(i.get("proposed_changes") or []) for i in items)
    high_risk = 0
    for i in items:
        for c in i.get("proposed_changes") or []:
            rl = str((c.get("approval_intent") or {}).get("risk_level") or "").lower()
            if rl == "high":
                high_risk += 1
    scopes_only_no_action = 0
    for i in items:
        pcs = i.get("proposed_changes") or []
        if not pcs:
            continue
        if all((c.get("change_type") or "").strip().lower() == "no_action_proposed" for c in pcs):
            scopes_only_no_action += 1
    return {
        "total_scopes": total_scopes,
        "scopes_with_changes": scopes_with_changes,
        "total_changes": total_change_rows,
        "high_risk": high_risk,
        "scopes_only_no_action": scopes_only_no_action,
    }


def _filter_conflict_scope_items(
    items: list[dict],
    *,
    scope_id: str,
) -> list[dict]:
    """Apply optional scope_id filter (same outer-scope behavior as proposed-changes)."""
    sid = (scope_id or "").strip()
    if not sid:
        return list(items)
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        if (item.get("scope_id") or "").strip() != sid:
            continue
        out.append(item)
    return out


def _merge_proposal_conflicts_into_items(
    items: list[dict],
    conflict_items: list[dict],
    *,
    conflicts_only: bool,
) -> list[dict]:
    """
    Attach scope_conflicts and per-proposal related_conflicts.
    When conflicts_only, drop scopes with no conflicting proposals and proposals without conflicts.
    """
    index: dict[tuple[str, str], dict] = {}
    for row in conflict_items:
        k = ((row.get("scope") or "").strip(), (row.get("scope_id") or "").strip())
        index[k] = row

    out: list[dict] = []
    for raw in items:
        k = ((raw.get("scope") or "").strip(), (raw.get("scope_id") or "").strip())
        crow = index.get(k)
        conflicts_list = list((crow or {}).get("conflicts") or [])
        item = dict(raw)
        item["scope_conflicts"] = conflicts_list

        new_pcs: list[dict] = []
        for c in item.get("proposed_changes") or []:
            ch = dict(c)
            cid = (ch.get("change_id") or "").strip()
            related = [
                cf
                for cf in conflicts_list
                if cid and cid in (cf.get("proposal_ids") or [])
            ]
            ch["related_conflicts"] = related
            ch["has_conflict"] = len(related) > 0
            if conflicts_only and not related:
                continue
            new_pcs.append(ch)
        item["proposed_changes"] = new_pcs

        if conflicts_only and not new_pcs:
            continue
        out.append(item)
    return out


def _summarize_ops_conflicts(items: list[dict]) -> dict[str, int]:
    scopes_with = 0
    total = 0
    hi = med = low = 0
    for item in items:
        cl = item.get("scope_conflicts") or []
        if not cl:
            continue
        scopes_with += 1
        total += len(cl)
        for cf in cl:
            s = (cf.get("severity") or "").strip().lower()
            if s == "high":
                hi += 1
            elif s == "medium":
                med += 1
            elif s == "low":
                low += 1
    return {
        "scopes_with_conflicts": scopes_with,
        "total_conflicts": total,
        "high_severity": hi,
        "medium_severity": med,
        "low_severity": low,
    }


def _merge_staleness_into_items(items: list[dict], staleness_rows: list[dict]) -> None:
    """Attach staleness_* fields to each proposed change when an annotation exists."""
    index: dict[tuple[str, str], dict[str, dict]] = {}
    for row in staleness_rows:
        scope = (row.get("scope") or "").strip()
        sid = (row.get("scope_id") or "").strip()
        by_cid: dict[str, dict] = {}
        for ann in row.get("staleness") or []:
            cid = (ann.get("change_id") or "").strip()
            if cid:
                by_cid[cid] = ann
        index[(scope, sid)] = by_cid

    for item in items:
        k = ((item.get("scope") or "").strip(), (item.get("scope_id") or "").strip())
        by_cid = index.get(k, {})
        for c in item.get("proposed_changes") or []:
            cid = (c.get("change_id") or "").strip()
            ann = by_cid.get(cid) if cid else None
            if not ann:
                continue
            c["staleness_status"] = ann.get("status")
            c["staleness_severity"] = ann.get("severity")
            c["staleness_summary"] = ann.get("summary")
            c["staleness_reason"] = ann.get("reason")
            c["staleness_signals"] = list(ann.get("signals") or [])
            c["staleness_recommendation"] = ann.get("recommendation")


def _filter_proposed_changes_by_staleness(items: list[dict], staleness_status: str) -> list[dict]:
    """Keep proposals whose staleness_status matches; drop empty scopes."""
    st = (staleness_status or "").strip().lower()
    if not st or st == "all":
        return items
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        new_pcs: list[dict] = []
        for c in item.get("proposed_changes") or []:
            got = (c.get("staleness_status") or "").strip().lower()
            if got == st:
                new_pcs.append(c)
        item["proposed_changes"] = new_pcs
        if new_pcs:
            out.append(item)
    return out


def _summarize_staleness_visible(items: list[dict]) -> dict[str, int | bool]:
    fresh = aging = stale = superseded = 0
    for i in items:
        for c in i.get("proposed_changes") or []:
            s = (c.get("staleness_status") or "").strip().lower()
            if s == "fresh":
                fresh += 1
            elif s == "aging":
                aging += 1
            elif s == "stale":
                stale += 1
            elif s == "superseded":
                superseded += 1
    return {
        "fresh": fresh,
        "aging": aging,
        "stale": stale,
        "superseded": superseded,
        "has_superseded": superseded > 0,
    }


def _merge_approval_readiness_into_items(items: list[dict], readiness_rows: list[dict]) -> None:
    """Attach readiness_* fields from proposal-approval-readiness items when present."""
    index: dict[tuple[str, str], dict[str, dict]] = {}
    for row in readiness_rows:
        scope = (row.get("scope") or "").strip()
        sid = (row.get("scope_id") or "").strip()
        by_cid: dict[str, dict] = {}
        for ann in row.get("approval_readiness") or []:
            cid = (ann.get("change_id") or "").strip()
            if cid:
                by_cid[cid] = ann
        index[(scope, sid)] = by_cid

    for item in items:
        k = ((item.get("scope") or "").strip(), (item.get("scope_id") or "").strip())
        by_cid = index.get(k, {})
        for c in item.get("proposed_changes") or []:
            cid = (c.get("change_id") or "").strip()
            ann = by_cid.get(cid) if cid else None
            if not ann:
                continue
            c["readiness_status"] = ann.get("status")
            c["readiness_severity"] = ann.get("severity")
            c["readiness_summary"] = ann.get("summary")
            c["readiness_blocking_reasons"] = list(ann.get("blocking_reasons") or [])
            c["readiness_warnings"] = list(ann.get("warnings") or [])
            c["readiness_required_actions"] = list(ann.get("required_actions") or [])
            c["readiness_recommendation"] = ann.get("recommendation")


def _filter_proposed_changes_by_readiness(items: list[dict], readiness_status: str) -> list[dict]:
    st = (readiness_status or "").strip().lower()
    if not st or st == "all":
        return items
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        new_pcs: list[dict] = []
        for c in item.get("proposed_changes") or []:
            got = (c.get("readiness_status") or "").strip().lower()
            if got == st:
                new_pcs.append(c)
        item["proposed_changes"] = new_pcs
        if new_pcs:
            out.append(item)
    return out


def _summarize_readiness_visible(items: list[dict]) -> dict[str, int]:
    ready = warnings = blocked = 0
    for i in items:
        for c in i.get("proposed_changes") or []:
            s = (c.get("readiness_status") or "").strip().lower()
            if s == "approval_ready":
                ready += 1
            elif s == "blocked_with_warnings":
                warnings += 1
            elif s == "blocked":
                blocked += 1
    return {
        "approval_ready": ready,
        "blocked_with_warnings": warnings,
        "blocked": blocked,
    }


def _merge_apply_planning_into_items(items: list[dict], planning_rows: list[dict]) -> None:
    """Attach planning_* fields from proposal-apply-planning scope rows when present."""
    index: dict[tuple[str, str], dict[str, dict]] = {}
    for row in planning_rows:
        scope = (row.get("scope") or "").strip()
        sid = (row.get("scope_id") or "").strip()
        by_cid: dict[str, dict] = {}
        for plan in row.get("apply_plans") or []:
            cid = (plan.get("change_id") or "").strip()
            if cid:
                by_cid[cid] = plan
        index[(scope, sid)] = by_cid

    for item in items:
        k = ((item.get("scope") or "").strip(), (item.get("scope_id") or "").strip())
        by_cid = index.get(k, {})
        for c in item.get("proposed_changes") or []:
            cid = (c.get("change_id") or "").strip()
            plan = by_cid.get(cid) if cid else None
            if not plan:
                continue
            c["planning_status"] = plan.get("status")
            c["planning_severity"] = plan.get("severity")
            c["planning_summary"] = plan.get("summary")
            c["planning_execution_readiness"] = plan.get("execution_readiness")
            c["planning_preflight_checks"] = list(plan.get("preflight_checks") or [])
            c["planning_dependencies"] = list(plan.get("dependencies") or [])
            c["planning_execution_sequence"] = list(plan.get("execution_sequence") or [])
            c["planning_rollback_plan"] = list(plan.get("rollback_plan") or [])
            c["planning_safety_notes"] = list(plan.get("safety_notes") or [])
            c["planning_recommendation"] = plan.get("recommendation")
            c["planning_blocking_reasons"] = list(plan.get("blocking_reasons") or [])


def _filter_proposed_changes_by_planning_status(items: list[dict], planning_status: str) -> list[dict]:
    st = (planning_status or "").strip().lower()
    if not st or st == "all":
        return items
    out: list[dict] = []
    for raw in items:
        item = dict(raw)
        new_pcs: list[dict] = []
        for c in item.get("proposed_changes") or []:
            got = (c.get("planning_status") or "").strip().lower()
            if got == st:
                new_pcs.append(c)
        item["proposed_changes"] = new_pcs
        if new_pcs:
            out.append(item)
    return out


def _summarize_apply_planning_visible(items: list[dict]) -> dict[str, int]:
    planned = blocked = combined = 0
    for i in items:
        for c in i.get("proposed_changes") or []:
            s = (c.get("planning_status") or "").strip().lower()
            if s == "planned":
                planned += 1
            elif s == "blocked_from_planning":
                blocked += 1
            elif s == "requires_combined_plan":
                combined += 1
    return {
        "planned": planned,
        "blocked_from_planning": blocked,
        "requires_combined_plan": combined,
    }


def _enrich_proposed_changes_with_audit(
    items: list[dict],
    *,
    tenant_id: Optional[str],
    db: Session,
) -> None:
    """Attach audit_history to each proposed change (same data as GET /api/proposed-change-audit)."""
    tid = (tenant_id or "").strip()
    if not tid:
        for item in items:
            for change in item.get("proposed_changes") or []:
                change["audit_history"] = []
        return

    for item in items:
        for change in item.get("proposed_changes") or []:
            cid = (change.get("change_id") or "").strip()
            if not cid:
                change["audit_history"] = []
                continue
            change["audit_history"] = get_proposed_change_audit(
                change_id=cid,
                tenant_id=tid,
                db=db,
            )


@router.get("/runs", response_class=HTMLResponse, name="ops_runs")
def ops_runs(
    request: Request,
    status: Optional[str] = Query(default=None),
    tenant_id: Optional[str] = Query(default=None),
    lead_id: Optional[str] = Query(default=None),
    pipeline_name: Optional[str] = Query(default=None),
    vertical_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    q = db.query(PipelineRun)
    if status:
        q = q.filter(PipelineRun.status == status.upper())
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id.strip())
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id.strip())
    if pipeline_name:
        q = q.filter(PipelineRun.pipeline_name == pipeline_name.strip())
    if vertical_id:
        q = q.filter(PipelineRun.vertical_id == vertical_id.strip())

    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()
    return templates.TemplateResponse(
        "ops_runs.html",
        {
            "request": request,
            "current_user": current_user,
            "runs": runs,
            "filters": {
                "status": status or "",
                "tenant_id": tenant_id or "",
                "lead_id": lead_id or "",
                "pipeline_name": pipeline_name or "",
                "vertical_id": vertical_id or "",
                "limit": limit,
            },
        },
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse, name="ops_run_detail")
def ops_run_detail(
    request: Request,
    run_id: int,
    tenant_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    payload = build_pipeline_run_debug_payload(db, run_id)
    review_state = get_review_state(pipeline_run_id=run_id, db=db)
    return templates.TemplateResponse(
        "ops_run_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "payload": payload,
            "run_id": run_id,
            "review_state": review_state,
            "tenant_id_filter": tenant_id or "",
        },
    )


@router.get("/anomalies", response_class=HTMLResponse, name="ops_anomalies")
def ops_anomalies(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    anomaly_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    resolved_type: Optional[AnomalyType] = None
    anomaly_type_clean = (anomaly_type or "").strip().upper()
    if anomaly_type_clean:
        try:
            resolved_type = AnomalyType(anomaly_type_clean)
        except ValueError:
            resolved_type = None

    anomalies = run_all(
        db,
        tenant_id=(tenant_id or "").strip() or None,
        anomaly_type=resolved_type,
    )
    items = [a.to_dict() for a in anomalies]
    total = len(items)
    items = items[:limit]

    return templates.TemplateResponse(
        "ops_anomalies.html",
        {
            "request": request,
            "current_user": current_user,
            "anomalies": items,
            "total": total,
            "shown_count": len(items),
            "anomaly_types": [t.value for t in AnomalyType],
            "filters": {
                "tenant_id": tenant_id or "",
                "anomaly_type": resolved_type.value if resolved_type else "",
                "limit": limit,
            },
        },
    )


@router.get("/intelligence", response_class=HTMLResponse, name="ops_intelligence")
def ops_intelligence(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    signal_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    resolved_signal_type: Optional[SignalType] = None
    signal_type_clean = (signal_type or "").strip().lower()
    if signal_type_clean:
        try:
            resolved_signal_type = SignalType(signal_type_clean)
        except ValueError:
            resolved_signal_type = None

    signals = run_intelligence_signals(
        db,
        tenant_id=(tenant_id or "").strip() or None,
        signal_type=resolved_signal_type,
    )
    items = [s.to_dict() for s in signals]
    total = len(items)
    items = items[:limit]

    return templates.TemplateResponse(
        "ops_intelligence.html",
        {
            "request": request,
            "current_user": current_user,
            "signals": items,
            "total": total,
            "shown_count": len(items),
            "signal_types": [t.value for t in SignalType],
            "filters": {
                "tenant_id": tenant_id or "",
                "signal_type": resolved_signal_type.value if resolved_signal_type else "",
                "limit": limit,
            },
        },
    )


@router.get("/review", response_class=HTMLResponse, name="ops_review")
def ops_review(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    review_priority: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    review_state: Optional[str] = Query(default=None),
    scope: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    priority_clean = (review_priority or "").strip().lower()
    if not priority_clean:
        priority_clean = (priority or "").strip().lower()
        if priority_clean == "critical":
            priority_clean = "high"
    if priority_clean not in {"high", "medium", "low"}:
        priority_clean = ""

    status_clean = (status or "").strip().upper()
    if not status_clean:
        status_clean = ""
    review_state_clean = (review_state or "").strip().lower()
    if review_state_clean not in {"", "pending", "acknowledged", "resolved", "ignored"}:
        review_state_clean = ""
    scope_clean = (scope or "").strip().lower()
    if scope_clean not in {"", "pipeline", "vertical"}:
        scope_clean = ""
    scope_id_clean = (scope_id or "").strip()

    items = build_inbox_items(
        db,
        tenant_id=(tenant_id or "").strip() or None,
        status=status_clean or None,
        priority=priority_clean or None,
        review_recommended_only=True,
        limit=limit,
        offset=0,
    )
    if review_state_clean:
        items = [i for i in items if (i.get("review_state") or "pending") == review_state_clean]
    if scope_clean and scope_id_clean:
        if scope_clean == "pipeline":
            items = [i for i in items if (i.get("pipeline_name") or "") == scope_id_clean]
        elif scope_clean == "vertical":
            items = [i for i in items if (i.get("vertical_id") or "") == scope_id_clean]

    review_state_counts = {
        "pending": 0,
        "acknowledged": 0,
        "resolved": 0,
        "ignored": 0,
    }
    for item in items:
        state = (item.get("review_state") or "pending").lower()
        if state in review_state_counts:
            review_state_counts[state] += 1

    return templates.TemplateResponse(
        "ops_review.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "filters": {
                "tenant_id": tenant_id or "",
                "review_priority": priority_clean,
                "status": status_clean,
                "review_state": review_state_clean,
                "scope": scope_clean,
                "scope_id": scope_id_clean,
                "limit": limit,
            },
            "priority_options": ["high", "medium", "low"],
            "status_options": ["FAILED", "NEEDS_REVIEW", "COMPLETED", "RUNNING"],
            "review_state_options": ["pending", "acknowledged", "resolved", "ignored"],
            "review_state_counts": review_state_counts,
        },
    )


@router.post("/review/state", name="ops_review_update_state")
def ops_review_update_state(
    pipeline_run_id: int = Form(...),
    tenant_id: str = Form(...),
    review_state_status: str = Form(...),
    review_state_note: Optional[str] = Form(default=None),
    tenant_id_filter: Optional[str] = Form(default=""),
    review_priority_filter: Optional[str] = Form(default=""),
    status_filter: Optional[str] = Form(default=""),
    review_state_filter: Optional[str] = Form(default=""),
    scope_filter: Optional[str] = Form(default=""),
    scope_id_filter: Optional[str] = Form(default=""),
    limit_filter: int = Form(default=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    resolved_status = (review_state_status or "").strip().lower()
    if resolved_status not in {"pending", "acknowledged", "resolved", "ignored"}:
        resolved_status = "pending"

    upsert_review_state(
        payload=ReviewStatePayload(
            pipeline_run_id=pipeline_run_id,
            tenant_id=(tenant_id or "").strip(),
            status=resolved_status,
            note=(review_state_note or "").strip() or None,
        ),
        db=db,
    )

    query_params = {
        "tenant_id": (tenant_id_filter or "").strip(),
        "review_priority": (review_priority_filter or "").strip(),
        "status": (status_filter or "").strip(),
        "review_state": (review_state_filter or "").strip(),
        "scope": (scope_filter or "").strip(),
        "scope_id": (scope_id_filter or "").strip(),
        "limit": limit_filter,
    }
    redirect_url = f"{router.url_path_for('ops_review')}?{urlencode(query_params)}"
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/runs/{run_id}/review-state", name="ops_run_update_state")
def ops_run_update_state(
    run_id: int,
    tenant_id: str = Form(...),
    review_state_status: str = Form(...),
    review_state_note: Optional[str] = Form(default=None),
    tenant_id_filter: Optional[str] = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    resolved_status = (review_state_status or "").strip().lower()
    if resolved_status not in {"pending", "acknowledged", "resolved", "ignored"}:
        resolved_status = "pending"

    upsert_review_state(
        payload=ReviewStatePayload(
            pipeline_run_id=run_id,
            tenant_id=(tenant_id or "").strip(),
            status=resolved_status,
            note=(review_state_note or "").strip() or None,
        ),
        db=db,
    )

    query_params = {}
    tenant_id_filter_clean = (tenant_id_filter or "").strip()
    if tenant_id_filter_clean:
        query_params["tenant_id"] = tenant_id_filter_clean

    redirect_url = str(router.url_path_for("ops_run_detail", run_id=run_id))
    if query_params:
        redirect_url = f"{redirect_url}?{urlencode(query_params)}"
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/focus", response_class=HTMLResponse, name="ops_focus")
def ops_focus(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    scope: str = Query(default="pipelines"),
    scope_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    scope_clean = (scope or "pipelines").strip().lower()
    if scope_clean not in {"pipelines", "verticals"}:
        scope_clean = "pipelines"

    priority_clean = (priority or "").strip().lower()
    if priority_clean not in {"critical", "high", "medium", "low"}:
        priority_clean = ""

    focus_response = (
        get_vertical_focus(
            tenant_id=tenant_id,
            top_n=limit,
            window_days=_OPS_API_WINDOW_DAYS,
            lookback_days=_OPS_API_LOOKBACK_DAYS,
            db=db,
        )
        if scope_clean == "verticals"
        else get_pipeline_focus(
            tenant_id=tenant_id,
            top_n=limit,
            window_days=_OPS_API_WINDOW_DAYS,
            lookback_days=_OPS_API_LOOKBACK_DAYS,
            db=db,
        )
    )
    items = focus_response.get("items", [])

    if priority_clean:
        items = [i for i in items if (i.get("severity") or "").lower() == priority_clean]
    scope_id_clean = (scope_id or "").strip()
    if scope_id_clean:
        items = [i for i in items if (i.get("scope_id") or "") == scope_id_clean]

    return templates.TemplateResponse(
        "ops_focus.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "total": focus_response.get("total", len(items)),
            "scope_label": "Pipelines" if scope_clean == "pipelines" else "Verticals",
            "scope_kind_singular": "pipeline" if scope_clean == "pipelines" else "vertical",
            "filters": {
                "tenant_id": tenant_id or "",
                "priority": priority_clean,
                "scope": scope_clean,
                "scope_id": scope_id_clean,
                "limit": limit,
            },
            "priority_options": ["critical", "high", "medium", "low"],
        },
    )


@router.get("/reasoning", response_class=HTMLResponse, name="ops_reasoning")
def ops_reasoning(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    scope: str = Query(default="pipelines"),
    category: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    scope_clean = (scope or "pipelines").strip().lower()
    if scope_clean not in {"pipelines", "verticals"}:
        scope_clean = "pipelines"

    category_clean = (category or "").strip().lower()
    scope_id_clean = (scope_id or "").strip()
    category_options = [
        "upstream_input_quality",
        "confidence_threshold_mismatch",
        "pricing_calibration_issue",
        "rule_coverage_gap",
        "operator_backlog",
        "anomaly_sensitivity_shift",
        "workflow_structure_inefficiency",
        "mixed_or_unclear",
    ]
    if category_clean and category_clean not in category_options:
        category_clean = ""

    response = (
        get_vertical_reasoning(
            tenant_id=tenant_id,
            limit=limit,
            window_days=_OPS_API_WINDOW_DAYS,
            lookback_days=_OPS_API_LOOKBACK_DAYS,
            db=db,
        )
        if scope_clean == "verticals"
        else get_pipeline_reasoning(
            tenant_id=tenant_id,
            limit=limit,
            window_days=_OPS_API_WINDOW_DAYS,
            lookback_days=_OPS_API_LOOKBACK_DAYS,
            db=db,
        )
    )
    items = _normalize_ops_reasoning_items(list(response.get("items") or []))
    api_total = int(response.get("total") or len(items))

    if scope_id_clean:
        items = [i for i in items if (i.get("scope_id") or "").strip() == scope_id_clean]

    if category_clean:
        filtered_items = []
        for item in items:
            reasoning_items = item.get("reasoning") or []
            filtered_reasoning = [r for r in reasoning_items if (r.get("category") or "").lower() == category_clean]
            if filtered_reasoning:
                cloned = dict(item)
                cloned["reasoning"] = filtered_reasoning
                filtered_items.append(cloned)
        items = filtered_items

    total_scopes = len(items)
    scopes_with_reasoning = sum(1 for i in items if len(i.get("reasoning") or []) > 0)
    scopes_with_high_confidence = sum(
        1
        for i in items
        if any((r.get("confidence") or "").lower() == "high" for r in (i.get("reasoning") or []))
    )
    scopes_mixed_only = sum(
        1
        for i in items
        if (i.get("reasoning") or [])
        and all((r.get("category") or "").lower() == "mixed_or_unclear" for r in (i.get("reasoning") or []))
    )

    return templates.TemplateResponse(
        "ops_reasoning.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "total": api_total,
            "scope_label": "Pipelines" if scope_clean == "pipelines" else "Verticals",
            "scope_kind_singular": "pipeline" if scope_clean == "pipelines" else "vertical",
            "summary_counts": {
                "total_scopes": total_scopes,
                "with_reasoning": scopes_with_reasoning,
                "high_confidence": scopes_with_high_confidence,
                "mixed_only": scopes_mixed_only,
            },
            "filters": {
                "tenant_id": tenant_id or "",
                "scope": scope_clean,
                "category": category_clean,
                "scope_id": scope_id_clean,
                "limit": limit,
            },
            "category_options": category_options,
        },
    )


@router.get("/control-suggestions", response_class=HTMLResponse, name="ops_control_suggestions")
def ops_control_suggestions(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    scope: str = Query(default="pipelines"),
    category: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    window_days: int = Query(default=7, ge=1, le=90),
    lookback_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    scope_clean = (scope or "pipelines").strip().lower()
    if scope_clean not in {"pipelines", "verticals"}:
        scope_clean = "pipelines"

    category_clean = (category or "").strip().lower()
    if category_clean and category_clean not in _CONTROL_SUGGESTION_CATEGORY_OPTIONS:
        category_clean = ""

    scope_id_clean = (scope_id or "").strip()

    tenant_param = (tenant_id or "").strip() or None

    if scope_clean == "verticals":
        envelope = get_vertical_control_suggestions(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
    else:
        envelope = get_pipeline_control_suggestions(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )

    raw_items = list(envelope.get("items") or [])
    items = _filter_control_suggestion_items(
        raw_items,
        category=category_clean,
        scope_id=scope_id_clean,
    )
    summary_counts = _summarize_control_suggestions(items)

    return templates.TemplateResponse(
        "ops_control_suggestions.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "api_total": envelope.get("total", len(raw_items)),
            "envelope": envelope,
            "scope_label": "Pipelines" if scope_clean == "pipelines" else "Verticals",
            "summary_counts": summary_counts,
            "filters": {
                "tenant_id": tenant_id or "",
                "scope": scope_clean,
                "category": category_clean,
                "scope_id": scope_id_clean,
                "limit": limit,
                "window_days": window_days,
                "lookback_days": lookback_days,
            },
            "category_options": _CONTROL_SUGGESTION_CATEGORY_OPTIONS,
        },
    )


@router.get("/simulation-preview", response_class=HTMLResponse, name="ops_simulation_preview")
def ops_simulation_preview(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    scope: str = Query(default="pipelines"),
    category: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    window_days: int = Query(default=7, ge=1, le=90),
    lookback_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    scope_clean = (scope or "pipelines").strip().lower()
    if scope_clean not in {"pipelines", "verticals"}:
        scope_clean = "pipelines"

    category_clean = (category or "").strip().lower()
    if category_clean and category_clean not in _CONTROL_SUGGESTION_CATEGORY_OPTIONS:
        category_clean = ""

    scope_id_clean = (scope_id or "").strip()
    tenant_param = (tenant_id or "").strip() or None

    if scope_clean == "verticals":
        envelope = get_vertical_simulation_previews(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
    else:
        envelope = get_pipeline_simulation_previews(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )

    raw_items = list(envelope.get("items") or [])
    items = _filter_simulation_preview_items(
        raw_items,
        category=category_clean,
        scope_id=scope_id_clean,
    )
    summary_counts = _summarize_simulation_preview(items)

    return templates.TemplateResponse(
        "ops_simulation_preview.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "api_total": envelope.get("total", len(raw_items)),
            "envelope": envelope,
            "scope_label": "Pipelines" if scope_clean == "pipelines" else "Verticals",
            "summary_counts": summary_counts,
            "filters": {
                "tenant_id": tenant_id or "",
                "scope": scope_clean,
                "category": category_clean,
                "scope_id": scope_id_clean,
                "limit": limit,
                "window_days": window_days,
                "lookback_days": lookback_days,
            },
            "category_options": _CONTROL_SUGGESTION_CATEGORY_OPTIONS,
        },
    )


@router.get("/proposed-changes", response_class=HTMLResponse, name="ops_proposed_changes")
def ops_proposed_changes(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    scope: str = Query(default="pipelines"),
    scope_id: Optional[str] = Query(default=None),
    change_id: Optional[str] = Query(default=None, description="Show only this proposal (change_id)"),
    limit: int = Query(default=50, ge=1, le=100),
    window_days: int = Query(default=7, ge=1, le=90),
    lookback_days: int = Query(default=30, ge=1, le=365),
    change_type: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    conflicts_only: Optional[str] = Query(default=None, description="yes / no — show only scopes/proposals with conflicts"),
    staleness_status: Optional[str] = Query(default=None, description="Filter by staleness status"),
    readiness_status: Optional[str] = Query(
        default=None,
        description="Filter by approval readiness status",
    ),
    planning_status: Optional[str] = Query(
        default=None,
        description="Filter by apply planning status",
    ),
    pc_action_error: Optional[str] = Query(default=None, description="Workflow action error (redirect)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    scope_clean = (scope or "pipelines").strip().lower()
    if scope_clean not in {"pipelines", "verticals"}:
        scope_clean = "pipelines"

    change_type_clean = (change_type or "").strip().lower()
    if change_type_clean and change_type_clean not in _PROPOSED_CHANGE_TYPE_OPTIONS:
        change_type_clean = ""

    risk_level_clean = (risk_level or "").strip().lower()
    if risk_level_clean and risk_level_clean not in _RISK_LEVEL_FILTER_OPTIONS:
        risk_level_clean = ""

    staleness_status_clean = (staleness_status or "").strip().lower()
    if staleness_status_clean not in _STALENESS_STATUS_FILTER_OPTIONS:
        staleness_status_clean = "all"

    readiness_status_clean = (readiness_status or "").strip().lower()
    if readiness_status_clean not in _READINESS_STATUS_FILTER_OPTIONS:
        readiness_status_clean = "all"

    planning_status_clean = (planning_status or "").strip().lower()
    if planning_status_clean not in _PLANNING_STATUS_FILTER_OPTIONS:
        planning_status_clean = "all"

    scope_id_clean = (scope_id or "").strip()
    tenant_param = (tenant_id or "").strip() or None
    change_id_clean = (change_id or "").strip() or None

    co_raw = (conflicts_only or "").strip().lower()
    conflicts_only_on = co_raw in ("1", "yes", "true", "on")

    if scope_clean == "verticals":
        envelope = get_vertical_proposed_changes(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        conflict_envelope = get_vertical_proposal_conflicts(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        staleness_envelope = get_vertical_proposal_staleness(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        readiness_envelope = get_vertical_approval_readiness(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        planning_envelope = get_vertical_apply_planning(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
    else:
        envelope = get_pipeline_proposed_changes(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        conflict_envelope = get_pipeline_proposal_conflicts(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        staleness_envelope = get_pipeline_proposal_staleness(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        readiness_envelope = get_pipeline_approval_readiness(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        planning_envelope = get_pipeline_apply_planning(
            tenant_id=tenant_param,
            window_days=window_days,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )

    raw_items = list(envelope.get("items") or [])
    items = _filter_proposed_change_items(
        raw_items,
        scope_id=scope_id_clean,
        change_type=change_type_clean,
        risk_level=risk_level_clean,
    )

    raw_conflict_items = list(conflict_envelope.get("items") or [])
    conflict_items = _filter_conflict_scope_items(
        raw_conflict_items,
        scope_id=scope_id_clean,
    )
    items = _merge_proposal_conflicts_into_items(
        items,
        conflict_items,
        conflicts_only=conflicts_only_on,
    )

    raw_staleness_items = list(staleness_envelope.get("items") or [])
    staleness_rows = _filter_conflict_scope_items(
        raw_staleness_items,
        scope_id=scope_id_clean,
    )
    _merge_staleness_into_items(items, staleness_rows)
    items = _filter_proposed_changes_by_staleness(items, staleness_status_clean)

    raw_readiness_items = list(readiness_envelope.get("items") or [])
    readiness_rows = _filter_conflict_scope_items(
        raw_readiness_items,
        scope_id=scope_id_clean,
    )
    _merge_approval_readiness_into_items(items, readiness_rows)
    items = _filter_proposed_changes_by_readiness(items, readiness_status_clean)

    raw_planning_items = list(planning_envelope.get("items") or [])
    planning_rows = _filter_conflict_scope_items(
        raw_planning_items,
        scope_id=scope_id_clean,
    )
    _merge_apply_planning_into_items(items, planning_rows)
    items = _filter_proposed_changes_by_planning_status(items, planning_status_clean)

    summary_counts = _summarize_proposed_changes(items)
    conflict_summary = _summarize_ops_conflicts(items)
    staleness_summary = _summarize_staleness_visible(items)
    readiness_summary = _summarize_readiness_visible(items)
    apply_planning_summary = _summarize_apply_planning_visible(items)

    _enrich_proposed_changes_with_audit(items, tenant_id=tenant_param, db=db)

    apply_intents_by_change_id = _load_apply_intent_map(db, tenant_param)
    execution_requests_by_change_id = _load_execution_request_map(db, tenant_param)
    execution_outcomes_by_change_id = _load_execution_outcome_map(db, tenant_param)
    execution_attempts_by_change_id = _load_execution_attempts_map(db, tenant_param)
    if change_id_clean:
        items = _filter_proposed_change_items_by_change_id(items, change_id_clean)

    change_types_flat: list[str] = []
    for i in items:
        for c in i.get("proposed_changes") or []:
            change_types_flat.append((c.get("change_type") or "").strip().lower())
    only_no_action_shown = bool(change_types_flat) and all(
        ct == "no_action_proposed" for ct in change_types_flat
    )

    return templates.TemplateResponse(
        "ops_proposed_changes.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "shown_count": len(items),
            "api_total": envelope.get("total", len(raw_items)),
            "envelope": envelope,
            "scope_label": "Pipelines" if scope_clean == "pipelines" else "Verticals",
            "summary_counts": summary_counts,
            "conflict_summary": conflict_summary,
            "staleness_summary": staleness_summary,
            "readiness_summary": readiness_summary,
            "apply_planning_summary": apply_planning_summary,
            "only_no_action_shown": only_no_action_shown,
            "apply_intents_by_change_id": apply_intents_by_change_id,
            "execution_requests_by_change_id": execution_requests_by_change_id,
            "execution_outcomes_by_change_id": execution_outcomes_by_change_id,
            "execution_attempts_by_change_id": execution_attempts_by_change_id,
            "filters": {
                "tenant_id": tenant_id or "",
                "scope": scope_clean,
                "scope_id": scope_id_clean,
                "change_id": change_id_clean or "",
                "limit": limit,
                "window_days": window_days,
                "lookback_days": lookback_days,
                "change_type": change_type_clean,
                "risk_level": risk_level_clean,
                "conflicts_only": "yes" if conflicts_only_on else "",
                "staleness_status": staleness_status_clean,
                "readiness_status": readiness_status_clean,
                "planning_status": planning_status_clean,
            },
            "change_type_options": _PROPOSED_CHANGE_TYPE_OPTIONS,
            "risk_level_options": _RISK_LEVEL_FILTER_OPTIONS,
            "staleness_status_options": _STALENESS_STATUS_FILTER_OPTIONS,
            "readiness_status_options": _READINESS_STATUS_FILTER_OPTIONS,
            "planning_status_options": _PLANNING_STATUS_FILTER_OPTIONS,
            "proposed_change_review_status_options": [
                "pending",
                "approved",
                "rejected",
                "archived",
                "ready_for_apply",
            ],
            "pc_action_error": (pc_action_error or "").strip() or None,
        },
    )


@router.get("/apply-intents", response_class=HTMLResponse, name="ops_apply_intents")
def ops_apply_intents(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    """Read-only table of persisted apply intents (same data as GET /api/proposed-change-apply-intents)."""
    tid = (tenant_id or "").strip()
    status_clean = (status or "").strip().lower()
    if status_clean not in _APPLY_INTENT_STATUS_FILTER_OPTIONS:
        status_clean = "all"
    rows: list[dict[str, Any]] = []
    if tid:
        st_arg = None if status_clean == "all" else status_clean
        rows = _query_apply_intents_for_ops_list(db, tenant_id=tid, status=st_arg)
    return templates.TemplateResponse(
        "ops_apply_intents.html",
        {
            "request": request,
            "current_user": current_user,
            "items": rows,
            "filters": {
                "tenant_id": tenant_id or "",
                "status": status_clean,
            },
            "status_options": _APPLY_INTENT_STATUS_FILTER_OPTIONS,
        },
    )


@router.get("/execution-requests", response_class=HTMLResponse, name="ops_execution_requests")
def ops_execution_requests(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    scope_type: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    """Read-only list of execution requests (same data as GET /api/proposed-change-execution-requests)."""
    tid = (tenant_id or "").strip()
    status_clean = (status or "").strip().lower()
    if status_clean not in _EXECUTION_REQUEST_STATUS_FILTER_OPTIONS:
        status_clean = "all"
    st_clean = (scope_type or "").strip().lower()
    if st_clean not in _EXECUTION_REQUEST_SCOPE_TYPE_FILTER_OPTIONS:
        st_clean = "all"
    sid_clean = (scope_id or "").strip()

    rows: list[dict[str, Any]] = []
    if tid:
        st_arg = None if status_clean == "all" else status_clean
        rows = _query_execution_requests_for_ops_list(
            db,
            tenant_id=tid,
            status=st_arg,
            scope_type=st_clean,
            scope_id=sid_clean or None,
        )

    return templates.TemplateResponse(
        "ops_execution_requests.html",
        {
            "request": request,
            "current_user": current_user,
            "items": rows,
            "filters": {
                "tenant_id": tenant_id or "",
                "status": status_clean,
                "scope_type": st_clean,
                "scope_id": sid_clean,
            },
            "status_options": _EXECUTION_REQUEST_STATUS_FILTER_OPTIONS,
            "scope_type_options": _EXECUTION_REQUEST_SCOPE_TYPE_FILTER_OPTIONS,
        },
    )


@router.get(
    "/execution-requests/{change_id:path}",
    response_class=HTMLResponse,
    name="ops_execution_request_detail",
)
def ops_execution_request_detail(
    request: Request,
    change_id: str,
    tenant_id: str = Query(..., description="Tenant that owns this request"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tid = (tenant_id or "").strip()
    cid = (change_id or "").strip()
    if not tid or not cid:
        raise HTTPException(status_code=400, detail="tenant_id and change_id are required")

    row = (
        db.query(ProposedChangeExecutionRequest)
        .filter(
            ProposedChangeExecutionRequest.tenant_id == tid,
            ProposedChangeExecutionRequest.change_id == cid,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Execution request not found")

    prepared = _prepare_execution_request_for_template(
        _execution_request_to_dict(row, include_snapshots=True)
    )
    return templates.TemplateResponse(
        "ops_execution_request_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "row": prepared,
        },
    )


@router.get("/execution-attempts", response_class=HTMLResponse, name="ops_execution_attempts")
def ops_execution_attempts(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    """Read-only list of execution attempts (same data as GET /api/proposed-change-execution-attempts)."""
    tid = (tenant_id or "").strip()
    status_clean = (status or "").strip().lower()
    if status_clean not in _EXECUTION_ATTEMPT_STATUS_FILTER_OPTIONS:
        status_clean = "all"

    rows: list[dict[str, Any]] = []
    if tid:
        st_arg = None if status_clean == "all" else status_clean
        rows = _query_execution_attempts_for_ops_list(
            db,
            tenant_id=tid,
            status=st_arg,
        )

    return templates.TemplateResponse(
        "ops_execution_attempts.html",
        {
            "request": request,
            "current_user": current_user,
            "items": rows,
            "filters": {
                "tenant_id": tenant_id or "",
                "status": status_clean,
            },
            "status_options": _EXECUTION_ATTEMPT_STATUS_FILTER_OPTIONS,
        },
    )


@router.get("/execution-outcomes", response_class=HTMLResponse, name="ops_execution_outcomes")
def ops_execution_outcomes(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    outcome_status: Optional[str] = Query(default=None),
    evaluation_status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    """Read-only list of execution outcomes (same data as GET /api/proposed-change-execution-outcomes)."""
    tid = (tenant_id or "").strip()
    os_clean = (outcome_status or "").strip().lower()
    if os_clean not in _EXECUTION_OUTCOME_STATUS_FILTER_OPTIONS:
        os_clean = "all"
    es_clean = (evaluation_status or "").strip().lower()
    if es_clean not in _EXECUTION_EVALUATION_STATUS_FILTER_OPTIONS:
        es_clean = "all"

    rows: list[dict[str, Any]] = []
    if tid:
        rows = _query_execution_outcomes_for_ops_list(
            db,
            tenant_id=tid,
            outcome_status=os_clean,
            evaluation_status=es_clean,
        )

    return templates.TemplateResponse(
        "ops_execution_outcomes.html",
        {
            "request": request,
            "current_user": current_user,
            "items": rows,
            "filters": {
                "tenant_id": tenant_id or "",
                "outcome_status": os_clean,
                "evaluation_status": es_clean,
            },
            "outcome_status_options": _EXECUTION_OUTCOME_STATUS_FILTER_OPTIONS,
            "evaluation_status_options": _EXECUTION_EVALUATION_STATUS_FILTER_OPTIONS,
        },
    )


@router.get(
    "/execution-outcomes/{change_id:path}",
    response_class=HTMLResponse,
    name="ops_execution_outcome_detail",
)
def ops_execution_outcome_detail(
    request: Request,
    change_id: str,
    tenant_id: str = Query(..., description="Tenant that owns this outcome"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    tid = (tenant_id or "").strip()
    cid = (change_id or "").strip()
    if not tid or not cid:
        raise HTTPException(status_code=400, detail="tenant_id and change_id are required")

    row = (
        db.query(ProposedChangeExecutionOutcome)
        .filter(
            ProposedChangeExecutionOutcome.tenant_id == tid,
            ProposedChangeExecutionOutcome.change_id == cid,
        )
        .order_by(ProposedChangeExecutionOutcome.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Execution outcome not found")

    prepared = _prepare_execution_outcome_for_template(_outcome_to_dict(row))
    return templates.TemplateResponse(
        "ops_execution_outcome_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "row": prepared,
        },
    )


@router.post("/proposed-changes/state", name="ops_proposed_changes_update_state")
def ops_proposed_changes_update_state(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    scope_type: str = Form(...),
    scope_id: str = Form(...),
    category: str = Form(...),
    change_type: str = Form(...),
    title: str = Form(...),
    pc_status: str = Form(..., alias="status"),
    note: Optional[str] = Form(default=None),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    tenant_clean = (tenant_id or "").strip()
    resolved_status = (pc_status or "").strip().lower()
    if resolved_status not in {"pending", "approved", "rejected", "archived", "ready_for_apply"}:
        resolved_status = "pending"

    if tenant_clean:
        upsert_proposed_change_state(
            payload=ProposedChangeStatePayload(
                tenant_id=tenant_clean,
                change_id=(change_id or "").strip(),
                scope_type=(scope_type or "").strip(),
                scope_id=(scope_id or "").strip(),
                category=(category or "").strip(),
                change_type=(change_type or "").strip(),
                title=(title or "").strip() or "—",
                status=resolved_status,
                note=(note or "").strip() or None,
                proposal_payload=None,
            ),
            db=db,
        )

    redirect_url = _ops_pc_list_redirect_url(flt)
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/proposed-changes/action/approve", name="ops_proposed_changes_action_approve")
def ops_proposed_changes_action_approve(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    approval_readiness_status: str = Form(...),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    try:
        pc_action_approve(
            ApproveRequest(
                tenant_id=(tenant_id or "").strip(),
                change_id=(change_id or "").strip(),
                approval_readiness_status=(approval_readiness_status or "").strip(),
                note=None,
            ),
            db=db,
        )
    except HTTPException as exc:
        return _ops_pc_action_error_redirect(flt, exc)
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/proposed-changes/action/reject", name="ops_proposed_changes_action_reject")
def ops_proposed_changes_action_reject(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    try:
        pc_action_reject(
            RejectRequest(
                tenant_id=(tenant_id or "").strip(),
                change_id=(change_id or "").strip(),
                note=None,
            ),
            db=db,
        )
    except HTTPException as exc:
        return _ops_pc_action_error_redirect(flt, exc)
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/proposed-changes/action/reopen", name="ops_proposed_changes_action_reopen")
def ops_proposed_changes_action_reopen(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    try:
        pc_action_reopen(
            ReopenRequest(
                tenant_id=(tenant_id or "").strip(),
                change_id=(change_id or "").strip(),
                note=None,
            ),
            db=db,
        )
    except HTTPException as exc:
        return _ops_pc_action_error_redirect(flt, exc)
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/proposed-changes/action/mark-ready-for-apply",
    name="ops_proposed_changes_action_mark_ready_for_apply",
)
def ops_proposed_changes_action_mark_ready_for_apply(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    apply_planning_status: str = Form(...),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    try:
        pc_action_mark_ready_for_apply(
            MarkReadyForApplyRequest(
                tenant_id=(tenant_id or "").strip(),
                change_id=(change_id or "").strip(),
                apply_planning_status=(apply_planning_status or "").strip(),
                note=None,
            ),
            db=db,
        )
    except HTTPException as exc:
        return _ops_pc_action_error_redirect(flt, exc)
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/proposed-changes/action/cancel-ready-for-apply",
    name="ops_proposed_changes_action_cancel_ready_for_apply",
)
def ops_proposed_changes_action_cancel_ready_for_apply(
    change_id: str = Form(...),
    tenant_id: str = Form(...),
    flt: OpsPCListFilters = Depends(get_ops_pc_list_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    _ = current_user
    try:
        pc_action_cancel_ready_for_apply(
            CancelReadyForApplyRequest(
                tenant_id=(tenant_id or "").strip(),
                change_id=(change_id or "").strip(),
                note=None,
            ),
            db=db,
        )
    except HTTPException as exc:
        return _ops_pc_action_error_redirect(flt, exc)
    return RedirectResponse(
        url=_ops_pc_list_redirect_url(flt),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/intelligence/health", response_class=HTMLResponse, name="ops_intelligence_health")
def ops_intelligence_health(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    health_status: Optional[str] = Query(default=None),
    pipeline_name: Optional[str] = Query(default=None),
    vertical_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    status_clean = (health_status or "").strip().lower()
    if status_clean not in {"healthy", "watch", "unhealthy"}:
        status_clean = ""

    pipeline_name_clean = (pipeline_name or "").strip().lower()
    vertical_id_clean = (vertical_id or "").strip().lower()

    items = [s.to_dict() for s in pipeline_health_summaries(db, tenant_id=(tenant_id or "").strip() or None)]

    if status_clean:
        items = [i for i in items if (i.get("health_status") or "").lower() == status_clean]
    if pipeline_name_clean:
        items = [i for i in items if pipeline_name_clean in (i.get("pipeline_name") or "").lower()]
    if vertical_id_clean:
        items = [i for i in items if vertical_id_clean in (i.get("vertical_id") or "").lower()]

    total = len(items)
    items = items[:limit]

    return templates.TemplateResponse(
        "ops_intelligence_health.html",
        {
            "request": request,
            "current_user": current_user,
            "items": items,
            "total": total,
            "shown_count": len(items),
            "filters": {
                "tenant_id": tenant_id or "",
                "health_status": status_clean,
                "pipeline_name": pipeline_name or "",
                "vertical_id": vertical_id or "",
                "limit": limit,
            },
            "health_status_options": ["healthy", "watch", "unhealthy"],
        },
    )
