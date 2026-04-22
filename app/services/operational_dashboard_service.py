"""
Operational overview for the tenant dashboard — mirrors frontend `product-flow` + offer/review
helpers so KPIs, intake series, status mix, and attention list stay consistent in one contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.lead import Lead
from app.models.pipeline_run import PipelineRun

# --- Status sets (keep aligned with frontend `lib/product-flow.ts`) ---

_OFFER_INCLUDED = {
    "NEW",
    "RUNNING",
    "PROCESSING",
    "SUCCEEDED",
    "COMPLETED",
    "READY",
    "QUOTE_READY",
    "SENT",
    "VIEWED",
    "PENDING",
    "PENDING_RESPONSE",
}
_REVIEW_INCLUDED = {
    "REVIEW_REQUIRED",
    "NEEDS_REVIEW",
    "PROCESSING_FAILED",
    "FAILED",
    "ERROR",
    "UNCERTAIN",
    "FLAGGED_DAMAGE",
}
_EXECUTION_INCLUDED = {"ACCEPTED", "SIGNED", "SCHEDULED", "IN_PROGRESS", "DONE"}
_ACCEPTED_OUTCOME_STATUSES = {"ACCEPTED", "SIGNED", "DONE", "COMPLETED"}
_REJECTED_OUTCOME_STATUSES = {"REJECTED", "DECLINED", "CANCELLED"}

LEADS_LIMIT = 200
JOBS_LIMIT = 200
PIPELINE_RUNS_LIMIT = 100
OFFER_FANOUT_CAP = 50
ATTENTION_LIMIT = 8


def _norm_status(value: object | None) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value).strip().upper()
    return str(value).strip().upper()


def _is_offer_flow(status: str) -> bool:
    return _norm_status(status) in _OFFER_INCLUDED


def _is_review_flow(status: str) -> bool:
    return _norm_status(status) in _REVIEW_INCLUDED


def _is_offer_bucket(status: str) -> bool:
    return _is_offer_flow(status) and not _is_review_flow(status)


def _is_execution_flow(status: str) -> bool:
    return _norm_status(status) in _EXECUTION_INCLUDED


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _max_dt(*vals: datetime | None) -> datetime | None:
    found: list[datetime] = []
    for v in vals:
        if v is None:
            continue
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        found.append(v.astimezone(timezone.utc))
    if not found:
        return None
    return max(found)


def _local_date_key(utc_instant: datetime, offset_minutes: int) -> str:
    if utc_instant.tzinfo is None:
        utc_instant = utc_instant.replace(tzinfo=timezone.utc)
    wall = utc_instant.astimezone(timezone.utc) + timedelta(minutes=offset_minutes)
    return wall.date().isoformat()


def _day_key_range_local(end_local: date, *, back_days: int) -> list[str]:
    """Calendar days from (end - back_days + 1) through end inclusive."""
    start = end_local - timedelta(days=back_days - 1)
    keys: list[str] = []
    d = start
    while d <= end_local:
        keys.append(d.isoformat())
        d += timedelta(days=1)
    return keys


def _local_today(now_utc: datetime, offset_minutes: int) -> date:
    wall = now_utc.astimezone(timezone.utc) + timedelta(minutes=offset_minutes)
    return wall.date()


def _dedupe_latest_by_lead(runs: list[PipelineRun]) -> list[PipelineRun]:
    by_lead: dict[str, PipelineRun] = {}
    for r in runs:
        lid = str(r.lead_id or "").strip()
        if not lid:
            continue
        cur = by_lead.get(lid)
        if cur is None or r.id > cur.id:
            by_lead[lid] = r
    return sorted(by_lead.values(), key=lambda x: -x.id)


def _review_urgency_score(status: str) -> int:
    u = _norm_status(status)
    if u in {"FAILED", "PROCESSING_FAILED", "ERROR"}:
        return 100
    if u in {"FLAGGED_DAMAGE", "UNCERTAIN"}:
        return 80
    if u in {"NEEDS_REVIEW", "REVIEW_REQUIRED"}:
        return 60
    return 40


@dataclass
class _LeadVm:
    id: str
    status: str
    name: str
    email: str
    created_at: datetime
    updated_at: datetime | None


def _load_leads(db: Session, tenant_id: str) -> list[_LeadVm]:
    rows = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(LEADS_LIMIT)
        .all()
    )
    return [
        _LeadVm(
            id=str(l.id),
            status=l.status,
            name=l.name,
            email=l.email,
            created_at=l.created_at,
            updated_at=l.updated_at,
        )
        for l in rows
    ]


def _load_jobs(db: Session, tenant_id: str) -> list[tuple[Job, Lead | None]]:
    return (
        db.query(Job, Lead)
        .outerjoin(Lead, Lead.id == Job.lead_id)
        .filter(Job.tenant_id == str(tenant_id))
        .order_by(Job.updated_at.desc(), Job.id.desc())
        .limit(JOBS_LIMIT)
        .all()
    )


def _load_runs(db: Session, tenant_id: str) -> list[PipelineRun]:
    return (
        db.query(PipelineRun)
        .filter(PipelineRun.tenant_id == str(tenant_id))
        .order_by(PipelineRun.id.desc())
        .limit(PIPELINE_RUNS_LIMIT)
        .all()
    )


def _load_runs_for_intake(
    db: Session, tenant_id: str, *, window_start_utc: datetime
) -> list[PipelineRun]:
    """
    Load all runs that can affect the intake chart/summary window.
    This avoids visual stretching from a short capped dataset.
    """
    return (
        db.query(PipelineRun)
        .filter(
            PipelineRun.tenant_id == str(tenant_id),
            PipelineRun.created_at.is_not(None),
            PipelineRun.created_at >= window_start_utc,
        )
        .order_by(PipelineRun.created_at.asc(), PipelineRun.id.asc())
        .all()
    )


def _build_offer_rows(
    runs: list[PipelineRun], lead_by_id: dict[str, _LeadVm]
) -> list[dict[str, Any]]:
    deduped = _dedupe_latest_by_lead(runs)
    lead_ids_with_run = {str(r.lead_id).strip() for r in deduped}
    latest_runs = [r for r in deduped if _is_offer_bucket(r.status)][:OFFER_FANOUT_CAP]

    rows: list[dict[str, Any]] = []
    for run in latest_runs:
        lid = str(run.lead_id or "").strip()
        lead = lead_by_id.get(lid)
        rows.append(
            {
                "run_id": run.id,
                "lead_id": lid,
                "status": run.status,
                "run_created": run.created_at,
                "run_updated": run.updated_at,
                "lead_updated": lead.updated_at if lead else None,
            }
        )

    for lead in lead_by_id.values():
        if len(rows) >= OFFER_FANOUT_CAP:
            break
        lid = lead.id.strip()
        if not lid or any(x["lead_id"] == lid for x in rows):
            continue
        if lid in lead_ids_with_run:
            continue
        if not _is_offer_bucket(lead.status):
            continue
        rows.append(
            {
                "run_id": 0,
                "lead_id": lid,
                "status": lead.status,
                "run_created": None,
                "run_updated": None,
                "lead_updated": lead.updated_at,
            }
        )
    return rows


def _build_attention_rows(
    runs: list[PipelineRun], lead_by_id: dict[str, _LeadVm], tenant_id: str
) -> list[dict[str, Any]]:
    deduped = _dedupe_latest_by_lead(runs)
    from_runs: list[dict[str, Any]] = []
    for run in deduped:
        if not _is_review_flow(run.status):
            continue
        lid = str(run.lead_id or "").strip()
        lead = lead_by_id.get(lid)
        eff = _max_dt(run.updated_at, run.completed_at, run.created_at)
        score = _review_urgency_score(run.status)
        from_runs.append(
            {
                "run_id": run.id,
                "lead_id": lid,
                "tenant_id": tenant_id,
                "status": run.status,
                "created_at": _iso_utc(run.created_at),
                "updated_at": _iso_utc(run.updated_at or run.completed_at),
                "customer_name": (lead.name or "").strip() if lead else "",
                "primary_href": f"/reviews/{lid}",
                "urgency_score": score,
                "effective_ts_ms": int(eff.timestamp() * 1000) if eff else 0,
            }
        )

    used = {r["lead_id"] for r in from_runs}
    for lead in lead_by_id.values():
        lid = lead.id.strip()
        if not lid or lid in used:
            continue
        if not _is_review_flow(lead.status):
            continue
        eff = _max_dt(lead.updated_at, lead.created_at)
        score = _review_urgency_score(lead.status)
        from_runs.append(
            {
                "run_id": 0,
                "lead_id": lid,
                "tenant_id": tenant_id,
                "status": lead.status,
                "created_at": _iso_utc(lead.created_at),
                "updated_at": _iso_utc(lead.updated_at),
                "customer_name": (lead.name or "").strip(),
                "primary_href": f"/reviews/{lid}",
                "urgency_score": score,
                "effective_ts_ms": int(eff.timestamp() * 1000) if eff else 0,
            }
        )
        used.add(lid)

    # Highest urgency first, then longest waiting (oldest effective change first).
    from_runs.sort(key=lambda r: (-r["urgency_score"], r["effective_ts_ms"]))
    return from_runs


def _count_in_window(
    timestamps: list[datetime | None],
    start: datetime,
    end: datetime,
    *,
    end_inclusive: bool = True,
) -> int:
    n = 0
    for t in timestamps:
        if t is None:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        t = t.astimezone(timezone.utc)
        if end_inclusive:
            if start <= t <= end:
                n += 1
        elif start <= t < end:
            n += 1
    return n


def _lead_outcome_metrics(
    db: Session,
    tenant_id: str,
    *,
    start_utc: datetime,
    end_utc_exclusive: datetime,
) -> dict[str, Any]:
    rows = (
        db.query(Lead.status)
        .filter(
            Lead.tenant_id == str(tenant_id),
            Lead.created_at >= start_utc,
            Lead.created_at < end_utc_exclusive,
        )
        .all()
    )
    total = len(rows)
    accepted = 0
    rejected = 0
    for row in rows:
        st = _norm_status(row.status)
        if st in _ACCEPTED_OUTCOME_STATUSES:
            accepted += 1
        elif st in _REJECTED_OUTCOME_STATUSES:
            rejected += 1
    decided = accepted + rejected
    accepted_rate = round((accepted / decided) * 100, 1) if decided > 0 else 0.0
    rejected_rate = round((rejected / decided) * 100, 1) if decided > 0 else 0.0
    return {
        "total_requests": total,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "decided_count": decided,
        "accepted_rate": accepted_rate,
        "rejected_rate": rejected_rate,
    }


def get_operational_dashboard(
    db: Session,
    tenant_id: str,
    *,
    chart_days: int = 30,
    timezone_offset_minutes: int = 0,
) -> dict[str, Any]:
    """
    timezone_offset_minutes: same as `-Date.getTimezoneOffset()` in JavaScript (minutes east of UTC).
    """
    cd = int(chart_days)
    safe_days = cd if cd in (7, 14, 30, 90) else 30

    now_utc = datetime.now(timezone.utc)
    leads = _load_leads(db, tenant_id)
    lead_by_id = {lv.id: lv for lv in leads}
    job_rows = _load_jobs(db, tenant_id)
    runs = _load_runs(db, tenant_id)

    offer_rows = _build_offer_rows(runs, lead_by_id)
    deduped = _dedupe_latest_by_lead(runs)
    attention_all = _build_attention_rows(runs, lead_by_id, str(tenant_id))
    attention = attention_all[:ATTENTION_LIMIT]

    # --- KPI primary values (match existing dashboard semantics) ---
    new_requests_total = len(leads)
    open_quotes_total = len(offer_rows)
    exec_jobs = [(j, ld) for j, ld in job_rows if _is_execution_flow(j.status)]
    active_jobs_total = len(exec_jobs)
    review_total = 0
    seen_review: set[str] = set()
    for run in deduped:
        if _is_review_flow(run.status):
            review_total += 1
            seen_review.add(str(run.lead_id).strip())
    for lead in lead_by_id.values():
        lid = lead.id.strip()
        if lid in seen_review:
            continue
        if _is_review_flow(lead.status):
            review_total += 1

    # --- 7d vs prior 7d inflow (lead created_at) ---
    boundary = now_utc - timedelta(days=7)
    prior_start = now_utc - timedelta(days=14)
    leads_created_last_7d = sum(
        1 for lv in leads if (ca := _as_utc(lv.created_at)) is not None and ca >= boundary
    )
    leads_created_prev_7d = sum(
        1
        for lv in leads
        if (ca := _as_utc(lv.created_at)) is not None and prior_start <= ca < boundary
    )

    # --- Offer activity (touched in window) ---
    def _offer_touch(o: dict[str, Any]) -> datetime | None:
        return _max_dt(o.get("run_updated"), o.get("run_created"), o.get("lead_updated"))

    offer_touches = [_offer_touch(o) for o in offer_rows]
    offers_touch_last_7d = _count_in_window(offer_touches, boundary, now_utc)
    offers_touch_prev_7d = _count_in_window(
        offer_touches, prior_start, boundary, end_inclusive=False
    )

    # --- Active jobs: updates in window (subset: execution flow jobs only) ---
    exec_job_updates = []
    for j, _ld in exec_jobs:
        exec_job_updates.append(j.updated_at)
    jobs_touch_last_7d = _count_in_window(exec_job_updates, boundary, now_utc)
    jobs_touch_prev_7d = _count_in_window(
        exec_job_updates, prior_start, boundary, end_inclusive=False
    )

    high_urgency_review = sum(
        1 for a in attention_all if int(a.get("urgency_score") or 0) >= 80
    )

    # --- Intake series + prior-period total (pipeline run created_at, local calendar) ---
    end_local = _local_today(now_utc, timezone_offset_minutes)
    current_keys = _day_key_range_local(end_local, back_days=safe_days)
    prior_end = end_local - timedelta(days=safe_days)
    prior_keys = _day_key_range_local(prior_end, back_days=safe_days)
    current_start_local = end_local - timedelta(days=safe_days - 1)
    current_end_local_exclusive = end_local + timedelta(days=1)
    current_start_utc = datetime.combine(
        current_start_local, datetime.min.time(), tzinfo=timezone.utc
    ) - timedelta(minutes=timezone_offset_minutes)
    current_end_utc_exclusive = datetime.combine(
        current_end_local_exclusive, datetime.min.time(), tzinfo=timezone.utc
    ) - timedelta(minutes=timezone_offset_minutes)
    intake_window_start_local = prior_end - timedelta(days=safe_days - 1)
    intake_window_start_utc = datetime.combine(
        intake_window_start_local, datetime.min.time(), tzinfo=timezone.utc
    ) - timedelta(minutes=timezone_offset_minutes)
    intake_runs = _load_runs_for_intake(
        db, tenant_id, window_start_utc=intake_window_start_utc
    )

    cur_counts = {k: 0 for k in current_keys}
    prior_total = 0
    prior_key_set = set(prior_keys)
    for run in intake_runs:
        if not run.created_at:
            continue
        ca = run.created_at
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        ca = ca.astimezone(timezone.utc)
        k_cur = _local_date_key(ca, timezone_offset_minutes)
        if k_cur in cur_counts:
            cur_counts[k_cur] += 1
        k_pr = _local_date_key(ca, timezone_offset_minutes)
        if k_pr in prior_key_set:
            prior_total += 1

    series_list: list[dict[str, Any]] = []
    counts_only = [cur_counts[k] for k in current_keys]
    peak_idx = 0
    peak_val = -1
    for i, k in enumerate(current_keys):
        c = cur_counts[k]
        if c > peak_val:
            peak_val = c
            peak_idx = i
        series_list.append({"day_key": k, "count": c})

    n_days = len(counts_only)
    total_intake = sum(counts_only)
    zero_days = sum(1 for x in counts_only if x == 0)
    avg_per_day = round(total_intake / n_days, 2) if n_days else 0.0
    peak_day_key = current_keys[peak_idx] if current_keys else ""

    # --- Status distribution (offers + jobs), same as dashboard merge ---
    by_status: dict[str, int] = {}
    for o in offer_rows:
        key = _norm_status(o["status"]).lower()
        if key:
            by_status[key] = by_status.get(key, 0) + 1
    for j, _ld in job_rows:
        key = _norm_status(j.status).lower()
        if key:
            by_status[key] = by_status.get(key, 0) + 1
    status_pairs = sorted(by_status.items(), key=lambda x: -x[1])[:6]

    scheduled_today = sum(
        1
        for j, _ld in exec_jobs
        if _norm_status(j.status) == "SCHEDULED"
    )
    outcome_metrics = _lead_outcome_metrics(
        db,
        tenant_id,
        start_utc=current_start_utc,
        end_utc_exclusive=current_end_utc_exclusive,
    )

    return {
        "generated_at": _iso_utc(now_utc),
        "timezone_offset_minutes": timezone_offset_minutes,
        "kpis": {
            "new_requests": {
                "value": new_requests_total,
                "inflow_last_7d": leads_created_last_7d,
                "inflow_prev_7d": leads_created_prev_7d,
                "inflow_delta": leads_created_last_7d - leads_created_prev_7d,
            },
            "open_quotes": {
                "value": open_quotes_total,
                "touched_last_7d": offers_touch_last_7d,
                "touched_prev_7d": offers_touch_prev_7d,
                "touched_delta": offers_touch_last_7d - offers_touch_prev_7d,
            },
            "active_jobs": {
                "value": active_jobs_total,
                "updated_last_7d": jobs_touch_last_7d,
                "updated_prev_7d": jobs_touch_prev_7d,
                "updated_delta": jobs_touch_last_7d - jobs_touch_prev_7d,
            },
            "review_queue": {
                "value": review_total,
                "high_urgency": high_urgency_review,
            },
        },
        "intake": {
            "range_days": safe_days,
            "series": series_list,
            "summary": {
                "total": total_intake,
                "avg_per_day": avg_per_day,
                "zero_day_count": zero_days,
                "peak_day_key": peak_day_key,
                "peak_count": max(counts_only) if counts_only else 0,
                "prior_range_total": prior_total,
                "prior_range_days": safe_days,
            },
        },
        "status_distribution": status_pairs,
        "attention": {
            "items": [
                {
                    "run_id": x["run_id"],
                    "lead_id": x["lead_id"],
                    "tenant_id": x["tenant_id"],
                    "status": x["status"],
                    "created_at": x["created_at"],
                    "updated_at": x["updated_at"],
                    "customer_name": x["customer_name"],
                    "primary_href": x["primary_href"],
                    "urgency_score": x["urgency_score"],
                }
                for x in attention
            ],
            "summary": {
                "total": review_total,
                "high_urgency": high_urgency_review,
                "shown": len(attention),
            },
        },
        "activity_strip": {
            "pipeline_runs_in_view": len(runs),
            "scheduled_jobs": scheduled_today,
        },
        "outcomes": {
            "range_days": safe_days,
            **outcome_metrics,
        },
        "meta": {
            "leads_limit": LEADS_LIMIT,
            "jobs_limit": JOBS_LIMIT,
            "pipeline_runs_limit": PIPELINE_RUNS_LIMIT,
        },
    }
