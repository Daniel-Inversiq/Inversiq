from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, asc, case, desc, func, or_
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.billing.features import is_subscription_accessible
from app.core.plan_catalog import resolve_plan_code
from app.core.settings import settings
from app.db import get_db
from app.dependencies.founder import require_platform_admin
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.tenant_settings import TenantSettings
from app.models.user import User
from app.services.founder_insights import get_tenant_health

router = APIRouter(
    prefix="/founder",
    tags=["founder"],
    dependencies=[Depends(require_platform_admin)],
)
templates = Jinja2Templates(directory="app/templates")


FOUNDER_TENANT_SORTS = frozenset(
    {"company", "created_at", "leads", "estimates", "revenue"}
)


_CANONICAL_PLAN_MRR_EUR: dict[str, int] = {
    "starter_99": 99,
    "pro_199": 199,
    "business_399": 399,
}


def _estimated_mrr_eur_for_resolved_plan(resolved: str | None) -> int:
    """List-price MRR per seat for canonical Paintly plans (estimate only)."""
    if not resolved:
        return _CANONICAL_PLAN_MRR_EUR["starter_99"]
    return _CANONICAL_PLAN_MRR_EUR.get(resolved, _CANONICAL_PLAN_MRR_EUR["starter_99"])


def _chart_label_short(name: str | None, *, max_len: int = 32) -> str:
    s = (name or "").strip() or "—"
    return s if len(s) <= max_len else f"{s[: max_len - 1]}…"


def _tenant_at_risk(last_lead_at: datetime | None, now: datetime, *, days: int = 30) -> bool:
    """No lead activity in the last `days` days (or never had leads)."""
    cutoff = now - timedelta(days=days)
    if last_lead_at is None:
        return True
    ll = last_lead_at
    if ll.tzinfo is None:
        ll = ll.replace(tzinfo=timezone.utc)
    return ll < cutoff


def _relative_created_label(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "—"
    d = dt
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    delta = now - d
    if delta.total_seconds() < 0:
        return "—"
    secs = int(delta.total_seconds())
    if secs < 3600:
        return "just now"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = delta.days
    if days == 1:
        return "1d ago"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    return d.strftime("%b %d, %Y")


def _format_eur(value: Any) -> str:
    """Display currency for founder UI (accepted quote totals; not payment data)."""
    if value is None:
        return "€0"
    try:
        if isinstance(value, Decimal):
            n = float(value)
        else:
            n = float(value)
    except (TypeError, ValueError):
        return "€0"
    if abs(n - round(n)) < 1e-9:
        return f"€{int(round(n)):,}"
    return f"€{n:,.2f}"


def _founder_tenants_list_url(
    request: Request,
    *,
    page: int,
    per_page: int,
    q: str | None,
    sort_by: str,
    sort_dir: str,
) -> str:
    params: dict[str, str | int] = {
        "page": page,
        "per_page": per_page,
        "sort": sort_by,
        "dir": sort_dir,
    }
    if q:
        params["q"] = q
    return str(request.url_for("founder_tenants")) + "?" + urlencode(params)


def _next_tenant_sort(sort_by: str, current_sort: str, current_dir: str) -> tuple[str, str]:
    if sort_by == current_sort:
        new_dir = "asc" if current_dir == "desc" else "desc"
        return sort_by, new_dir
    if sort_by == "company":
        return sort_by, "asc"
    return sort_by, "desc"


def _sort_href_map(
    request: Request,
    *,
    q: str | None,
    per_page: int,
    current_sort: str,
    current_dir: str,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in ("company", "created_at", "leads", "estimates", "revenue"):
        ns, nd = _next_tenant_sort(col, current_sort, current_dir)
        out[col] = _founder_tenants_list_url(
            request,
            page=1,
            per_page=per_page,
            q=q,
            sort_by=ns,
            sort_dir=nd,
        )
    return out


def _owner_candidates_subquery(db: Session):
    """
    Pick one owner-like user per tenant:
    1) user.email matching tenant.email (same tenant)
    2) otherwise earliest created user for tenant
    """
    owner_ranked = (
        db.query(
            User.tenant_id.label("tenant_id"),
            User.id.label("owner_user_id"),
            User.email.label("owner_email"),
            User.company_name.label("owner_name"),
            User.created_at.label("owner_created_at"),
            func.row_number()
            .over(
                partition_by=User.tenant_id,
                order_by=(
                    case(
                        (
                            func.lower(func.coalesce(User.email, ""))
                            == func.lower(func.coalesce(Tenant.email, "")),
                            0,
                        ),
                        else_=1,
                    ),
                    User.created_at.asc(),
                    User.id.asc(),
                ),
            )
            .label("rn"),
        )
        .join(Tenant, Tenant.id == User.tenant_id)
        .subquery()
    )
    return (
        db.query(
            owner_ranked.c.tenant_id,
            owner_ranked.c.owner_user_id,
            owner_ranked.c.owner_email,
            owner_ranked.c.owner_name,
            owner_ranked.c.owner_created_at,
        )
        .filter(owner_ranked.c.rn == 1)
        .subquery()
    )


def _is_tenant_active(
    *,
    subscription_status: str | None,
    trial_ends_at: datetime | None,
    last_lead_at: datetime | None,
    active_window_days: int = 30,
) -> bool:
    # Prefer billing accessibility when billing state is present.
    has_billing_state = bool((subscription_status or "").strip()) or trial_ends_at is not None
    if has_billing_state:
        return is_subscription_accessible(subscription_status, trial_ends_at)

    if last_lead_at is None:
        return False
    return last_lead_at >= datetime.now(timezone.utc) - timedelta(days=active_window_days)


@router.get("", name="founder_dashboard")
def founder_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now_utc = datetime.now(timezone.utc)
    seven_days_ago = now_utc - timedelta(days=7)

    total_tenants = db.query(func.count(Tenant.id)).scalar() or 0
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    total_estimates = (
        db.query(func.count(Lead.id)).filter(Lead.estimate_json.is_not(None)).scalar() or 0
    )
    new_signups_7d = (
        db.query(func.count(Tenant.id))
        .filter(Tenant.created_at >= seven_days_ago)
        .scalar()
        or 0
    )

    plan_counts_raw = (
        db.query(Tenant.plan_code.label("plan_code"), func.count(Tenant.id).label("count"))
        .group_by(Tenant.plan_code)
        .all()
    )
    free_count = 0
    pro_count = 0
    business_count = 0
    for row in plan_counts_raw:
        resolved = resolve_plan_code(row.plan_code)
        if resolved == "pro_199":
            pro_count += row.count
        elif resolved == "business_399":
            business_count += row.count
        else:
            free_count += row.count

    tenant_activity_rows = (
        db.query(
            Tenant.id.label("tenant_id"),
            Tenant.subscription_status,
            Tenant.trial_ends_at,
            func.max(Lead.created_at).label("last_lead_at"),
        )
        .outerjoin(Lead, Lead.tenant_id == Tenant.id)
        .group_by(Tenant.id, Tenant.subscription_status, Tenant.trial_ends_at)
        .all()
    )

    active_tenants = sum(
        1
        for row in tenant_activity_rows
        if _is_tenant_active(
            subscription_status=row.subscription_status,
            trial_ends_at=row.trial_ends_at,
            last_lead_at=row.last_lead_at,
        )
    )

    thirty_days_ago = now_utc - timedelta(days=30)
    revenue_row = (
        db.query(
            func.coalesce(func.sum(Lead.final_price), 0).label("accepted_total"),
            func.coalesce(
                func.sum(
                    case((Lead.accepted_at >= thirty_days_ago, Lead.final_price), else_=0)
                ),
                0,
            ).label("accepted_30d"),
        )
        .filter(Lead.accepted_at.is_not(None))
        .one()
    )
    accepted_total = revenue_row.accepted_total
    accepted_30d = revenue_row.accepted_30d

    st = func.lower(func.coalesce(Tenant.subscription_status, ""))
    billing_status_row = (
        db.query(
            func.coalesce(func.sum(case((st == "active", 1), else_=0)), 0).label(
                "paying"
            ),
            func.coalesce(func.sum(case((st == "trialing", 1), else_=0)), 0).label(
                "trialing"
            ),
            func.coalesce(func.sum(case((st == "canceled", 1), else_=0)), 0).label(
                "canceled"
            ),
            func.coalesce(func.sum(case((st == "past_due", 1), else_=0)), 0).label(
                "past_due"
            ),
        )
        .select_from(Tenant)
        .one()
    )
    paying_n = int(billing_status_row.paying or 0)
    trialing_n = int(billing_status_row.trialing or 0)
    canceled_n = int(billing_status_row.canceled or 0)
    past_due_n = int(billing_status_row.past_due or 0)

    active_plan_groups = (
        db.query(Tenant.plan_code, func.count(Tenant.id).label("n"))
        .filter(st == "active")
        .group_by(Tenant.plan_code)
        .all()
    )
    estimated_mrr = sum(
        _estimated_mrr_eur_for_resolved_plan(resolve_plan_code(row.plan_code))
        * int(row.n or 0)
        for row in active_plan_groups
    )
    estimated_arr = estimated_mrr * 12

    has_accepted_revenue = float(accepted_total or 0) > 0

    lc_agg = func.count(Lead.id).label("lc")
    top_leads_rows = (
        db.query(
            func.coalesce(Tenant.company_name, Tenant.name).label("nm"),
            lc_agg,
        )
        .select_from(Tenant)
        .join(Lead, Lead.tenant_id == Tenant.id)
        .group_by(Tenant.id, Tenant.company_name, Tenant.name)
        .order_by(desc(lc_agg))
        .limit(10)
        .all()
    )
    top_leads_labels = [_chart_label_short(r.nm) for r in top_leads_rows]
    top_leads_values = [int(r.lc or 0) for r in top_leads_rows]

    if has_accepted_revenue:
        rev_sum = func.coalesce(func.sum(Lead.final_price), 0).label("rev")
        top_bar_rows = (
            db.query(
                func.coalesce(Tenant.company_name, Tenant.name).label("nm"),
                rev_sum,
            )
            .select_from(Tenant)
            .join(Lead, Lead.tenant_id == Tenant.id)
            .filter(Lead.accepted_at.is_not(None))
            .group_by(Tenant.id, Tenant.company_name, Tenant.name)
            .order_by(desc(rev_sum))
            .limit(10)
            .all()
        )
        top_bar_title = "Top tenants by accepted quote value"
        top_bar_kind = "revenue"
        top_bar_labels = [_chart_label_short(r.nm) for r in top_bar_rows]
        top_bar_values = [float(r.rev or 0) for r in top_bar_rows]
    else:
        est_cnt = func.sum(
            case((Lead.estimate_json.is_not(None), 1), else_=0)
        ).label("ec")
        top_bar_rows = (
            db.query(
                func.coalesce(Tenant.company_name, Tenant.name).label("nm"),
                est_cnt,
            )
            .select_from(Tenant)
            .join(Lead, Lead.tenant_id == Tenant.id)
            .group_by(Tenant.id, Tenant.company_name, Tenant.name)
            .order_by(desc(est_cnt))
            .limit(10)
            .all()
        )
        top_bar_title = "Top tenants by estimates"
        top_bar_kind = "estimates"
        top_bar_labels = [_chart_label_short(r.nm) for r in top_bar_rows]
        top_bar_values = [int(r.ec or 0) for r in top_bar_rows]

    charts_payload = {
        "plan": {
            "labels": ["Starter", "Pro", "Business"],
            "values": [free_count, pro_count, business_count],
        },
        "status": {
            "labels": ["Active", "Trialing", "Past due", "Canceled"],
            "values": [paying_n, trialing_n, past_due_n, canceled_n],
        },
        "topLeads": {
            "labels": top_leads_labels,
            "values": top_leads_values,
            "empty": len(top_leads_rows) == 0,
        },
        "topBar": {
            "title": top_bar_title,
            "kind": top_bar_kind,
            "labels": top_bar_labels,
            "values": top_bar_values,
            "empty": len(top_bar_rows) == 0,
        },
    }
    charts_json = json.dumps(charts_payload, ensure_ascii=False)

    at_risk_tenants: list[dict[str, str]] = []
    for tenant_row in db.query(Tenant).all():
        health, reason = get_tenant_health(db, tenant_row.id)
        if health == "at_risk":
            at_risk_tenants.append(
                {
                    "id": tenant_row.id,
                    "name": tenant_row.company_name or tenant_row.name,
                    "reason": reason,
                }
            )

    return templates.TemplateResponse(
        "founder/dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "charts_json": charts_json,
            "at_risk_tenants": at_risk_tenants,
            "stats": {
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "free_tenants": free_count,
                "pro_tenants": pro_count,
                "business_tenants": business_count,
                "total_leads": total_leads,
                "total_estimates": total_estimates,
                "new_signups_7d": new_signups_7d,
                "accepted_quote_value_fmt": _format_eur(accepted_total),
                "accepted_quote_value_30d_fmt": _format_eur(accepted_30d),
                "billing_paying_tenants": paying_n,
                "billing_trialing_tenants": trialing_n,
                "billing_canceled_tenants": canceled_n,
                "billing_past_due_tenants": past_due_n,
                "estimated_mrr_fmt": _format_eur(estimated_mrr),
                "estimated_arr_fmt": _format_eur(estimated_arr),
            },
        },
    )


@router.get("/tenants", name="founder_tenants")
def founder_tenants(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="created_at"),
    dir_param: str = Query(default="desc", alias="dir"),
):
    q_clean = (q or "").strip()
    per_page_n = per_page
    sort_by = sort if sort in FOUNDER_TENANT_SORTS else "created_at"
    sort_dir = dir_param if dir_param in ("asc", "desc") else "desc"

    now_utc = datetime.now(timezone.utc)
    seven_days_ago = now_utc - timedelta(days=7)

    owner_sq = _owner_candidates_subquery(db)

    lead_7d_sq = (
        db.query(
            Lead.tenant_id.label("tenant_id"),
            func.count(Lead.id).label("leads_7d"),
        )
        .filter(Lead.created_at >= seven_days_ago)
        .group_by(Lead.tenant_id)
        .subquery()
    )

    accepted_leads_sq = (
        db.query(
            Lead.tenant_id.label("tenant_id"),
            func.count(Lead.id).label("accepted_leads"),
        )
        .filter(Lead.accepted_at.is_not(None))
        .group_by(Lead.tenant_id)
        .subquery()
    )

    lead_stats_sq = (
        db.query(
            Lead.tenant_id.label("tenant_id"),
            func.count(Lead.id).label("lead_count"),
            func.sum(case((Lead.estimate_json.is_not(None), 1), else_=0)).label(
                "estimate_count"
            ),
            func.max(Lead.created_at).label("last_lead_at"),
        )
        .group_by(Lead.tenant_id)
        .subquery()
    )

    accepted_revenue_sq = (
        db.query(
            Lead.tenant_id.label("tenant_id"),
            func.coalesce(func.sum(Lead.final_price), 0).label("accepted_revenue"),
        )
        .filter(Lead.accepted_at.is_not(None))
        .group_by(Lead.tenant_id)
        .subquery()
    )

    base = (
        db.query(
            Tenant,
            owner_sq.c.owner_name,
            owner_sq.c.owner_email,
            lead_stats_sq.c.lead_count,
            lead_stats_sq.c.estimate_count,
            lead_stats_sq.c.last_lead_at,
            accepted_revenue_sq.c.accepted_revenue,
            lead_7d_sq.c.leads_7d,
            accepted_leads_sq.c.accepted_leads,
        )
        .outerjoin(owner_sq, owner_sq.c.tenant_id == Tenant.id)
        .outerjoin(lead_stats_sq, lead_stats_sq.c.tenant_id == Tenant.id)
        .outerjoin(
            accepted_revenue_sq, accepted_revenue_sq.c.tenant_id == Tenant.id
        )
        .outerjoin(lead_7d_sq, lead_7d_sq.c.tenant_id == Tenant.id)
        .outerjoin(accepted_leads_sq, accepted_leads_sq.c.tenant_id == Tenant.id)
    )

    if q_clean:
        pattern = f"%{q_clean}%"
        base = base.filter(
            or_(
                Tenant.company_name.ilike(pattern),
                Tenant.name.ilike(pattern),
                Tenant.email.ilike(pattern),
                Tenant.slug.ilike(pattern),
                owner_sq.c.owner_email.ilike(pattern),
            )
        )

    total = base.count()
    total_pages = (total + per_page_n - 1) // per_page_n if total else 0
    page_n = page
    if total_pages:
        page_n = min(page_n, total_pages)

    company_sort_col = func.lower(func.coalesce(Tenant.company_name, Tenant.name))
    lead_count_ord = func.coalesce(lead_stats_sq.c.lead_count, 0)
    estimate_count_ord = func.coalesce(lead_stats_sq.c.estimate_count, 0)
    revenue_ord = func.coalesce(accepted_revenue_sq.c.accepted_revenue, 0)
    if sort_by == "company":
        primary_ord = asc(company_sort_col) if sort_dir == "asc" else desc(company_sort_col)
    elif sort_by == "created_at":
        primary_ord = asc(Tenant.created_at) if sort_dir == "asc" else desc(Tenant.created_at)
    elif sort_by == "leads":
        primary_ord = asc(lead_count_ord) if sort_dir == "asc" else desc(lead_count_ord)
    elif sort_by == "estimates":
        primary_ord = asc(estimate_count_ord) if sort_dir == "asc" else desc(estimate_count_ord)
    elif sort_by == "revenue":
        primary_ord = asc(revenue_ord) if sort_dir == "asc" else desc(revenue_ord)
    else:
        primary_ord = desc(Tenant.created_at)

    rows = (
        base.order_by(primary_ord, desc(Tenant.id))
        .offset((page_n - 1) * per_page_n)
        .limit(per_page_n)
        .all()
    )

    platform_rev_total = (
        db.query(func.coalesce(func.sum(Lead.final_price), 0))
        .filter(Lead.accepted_at.is_not(None))
        .scalar()
        or 0
    )
    use_rev_top = float(platform_rev_total) > 0

    if use_rev_top:
        rev_sum = func.coalesce(func.sum(Lead.final_price), 0).label("top_val")
        top_rows = (
            db.query(
                Tenant.id.label("tid"),
                func.coalesce(Tenant.company_name, Tenant.name).label("nm"),
                rev_sum,
            )
            .select_from(Tenant)
            .join(Lead, Lead.tenant_id == Tenant.id)
            .filter(Lead.accepted_at.is_not(None))
            .group_by(Tenant.id, Tenant.company_name, Tenant.name)
            .order_by(desc(rev_sum))
            .limit(3)
            .all()
        )
        top_performers = [
            {
                "id": r.tid,
                "company_name": r.nm,
                "kind": "revenue",
                "value": float(r.top_val or 0),
                "label": _format_eur(r.top_val),
            }
            for r in top_rows
        ]
    else:
        lc = func.count(Lead.id).label("top_val")
        top_rows = (
            db.query(
                Tenant.id.label("tid"),
                func.coalesce(Tenant.company_name, Tenant.name).label("nm"),
                lc,
            )
            .select_from(Tenant)
            .join(Lead, Lead.tenant_id == Tenant.id)
            .group_by(Tenant.id, Tenant.company_name, Tenant.name)
            .order_by(desc(lc))
            .limit(3)
            .all()
        )
        top_performers = [
            {
                "id": r.tid,
                "company_name": r.nm,
                "kind": "leads",
                "value": int(r.top_val or 0),
                "label": str(int(r.top_val or 0)),
            }
            for r in top_rows
        ]

    tenants = []
    for row in rows:
        tenant: Tenant = row[0]
        owner_name = row.owner_name or tenant.company_name or tenant.name
        owner_email = row.owner_email or tenant.email
        lead_count = int(row.lead_count or 0)
        estimate_count = int(row.estimate_count or 0)
        accepted_revenue = row.accepted_revenue
        accepted_revenue_f = float(accepted_revenue or 0)
        last_lead_at = row.last_lead_at
        leads_7d = int(row.leads_7d or 0)
        accepted_leads = int(row.accepted_leads or 0)
        conversion_pct = (
            round(100.0 * accepted_leads / lead_count, 1) if lead_count else None
        )
        at_risk = _tenant_at_risk(last_lead_at, now_utc)
        status = (
            "active"
            if _is_tenant_active(
                subscription_status=tenant.subscription_status,
                trial_ends_at=tenant.trial_ends_at,
                last_lead_at=last_lead_at,
            )
            else "inactive"
        )

        health, health_reason = get_tenant_health(db, tenant.id)

        tenants.append(
            {
                "id": tenant.id,
                "company_name": tenant.company_name or tenant.name,
                "owner_name": owner_name,
                "owner_email": owner_email,
                "phone": tenant.phone,
                "slug": tenant.slug,
                "plan_tier": resolve_plan_code(tenant.plan_code),
                "status": status,
                "created_at": tenant.created_at,
                "lead_count": lead_count,
                "leads_7d": leads_7d,
                "accepted_leads": accepted_leads,
                "conversion_pct": conversion_pct,
                "at_risk": at_risk,
                "estimate_count": estimate_count,
                "accepted_revenue": accepted_revenue_f,
                "accepted_revenue_fmt": _format_eur(accepted_revenue),
                "created_relative": _relative_created_label(tenant.created_at, now_utc),
                "health": health,
                "health_reason": health_reason,
            }
        )

    showing_from = (page_n - 1) * per_page_n + 1 if total else 0
    showing_to = min(page_n * per_page_n, total) if total else 0

    url_prev = (
        _founder_tenants_list_url(
            request,
            page=page_n - 1,
            per_page=per_page_n,
            q=q_clean or None,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        if page_n > 1
        else None
    )
    url_next = (
        _founder_tenants_list_url(
            request,
            page=page_n + 1,
            per_page=per_page_n,
            q=q_clean or None,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        if total_pages and page_n < total_pages
        else None
    )

    sort_href = _sort_href_map(
        request,
        q=q_clean or None,
        per_page=per_page_n,
        current_sort=sort_by,
        current_dir=sort_dir,
    )

    return templates.TemplateResponse(
        "founder/tenants_list.html",
        {
            "request": request,
            "current_user": current_user,
            "tenants": tenants,
            "top_performers": top_performers,
            "top_performers_mode": "revenue" if use_rev_top else "leads",
            "q": q_clean,
            "page": page_n,
            "per_page": per_page_n,
            "total": total,
            "total_pages": total_pages,
            "showing_from": showing_from,
            "showing_to": showing_to,
            "url_prev": url_prev,
            "url_next": url_next,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "sort_href": sort_href,
        },
    )


@router.get("/tenants/{tenant_id}", name="founder_tenant_detail")
def founder_tenant_detail(
    tenant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    owner_sq = _owner_candidates_subquery(db)
    owner_row = (
        db.query(owner_sq)
        .filter(owner_sq.c.tenant_id == tenant_id)
        .first()
    )

    branding = (
        db.query(TenantSettings)
        .filter(TenantSettings.tenant_id == tenant_id)
        .first()
    )

    recent_leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(40)
        .all()
    )

    app_public_origin = settings.APP_PUBLIC_BASE_URL.rstrip("/")
    recent_quote_rows = []
    for lead in recent_leads:
        pub_url = None
        if getattr(lead, "public_token", None):
            pub_url = f"{app_public_origin}/e/{lead.public_token}"
        recent_quote_rows.append(
            {
                "lead": lead,
                "price_fmt": _format_eur(lead.final_price)
                if lead.final_price is not None
                else "—",
                "public_url": pub_url,
            }
        )

    owner_info = {
        "name": (
            (owner_row.owner_name if owner_row else None)
            or tenant.company_name
            or tenant.name
        ),
        "email": (owner_row.owner_email if owner_row else None) or tenant.email,
    }

    subscription_info = {
        "stripe_customer_id": tenant.stripe_customer_id,
        "stripe_subscription_id": tenant.stripe_subscription_id,
        "subscription_status": tenant.subscription_status,
        "plan_code": resolve_plan_code(tenant.plan_code),
        "trial_ends_at": tenant.trial_ends_at,
    }

    total_leads = (
        db.query(func.count(Lead.id)).filter(Lead.tenant_id == tenant_id).scalar() or 0
    )
    total_estimates = (
        db.query(func.count(Lead.id))
        .filter(Lead.tenant_id == tenant_id, Lead.estimate_json.is_not(None))
        .scalar()
        or 0
    )

    now_utc = datetime.now(timezone.utc)
    thirty_days_ago = now_utc - timedelta(days=30)
    revenue_agg = (
        db.query(
            func.coalesce(func.sum(Lead.final_price), 0).label("revenue_total"),
            func.coalesce(
                func.sum(
                    case((Lead.accepted_at >= thirty_days_ago, Lead.final_price), else_=0)
                ),
                0,
            ).label("revenue_30d"),
            func.count(Lead.id).label("accepted_count"),
        )
        .filter(Lead.tenant_id == tenant_id, Lead.accepted_at.is_not(None))
        .one()
    )
    rev_total = revenue_agg.revenue_total
    rev_30d = revenue_agg.revenue_30d
    accepted_n = int(revenue_agg.accepted_count or 0)
    avg_accepted = None
    if accepted_n > 0:
        avg_accepted = float(rev_total) / accepted_n

    activity_row = (
        db.query(
            func.coalesce(
                func.sum(case((Lead.created_at >= thirty_days_ago, 1), else_=0)), 0
            ).label("leads_30d"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Lead.created_at >= thirty_days_ago,
                                Lead.estimate_json.is_not(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("estimates_30d"),
            func.coalesce(
                func.sum(case((Lead.accepted_at >= thirty_days_ago, 1), else_=0)), 0
            ).label("accepted_30d"),
        )
        .filter(Lead.tenant_id == tenant_id)
        .one()
    )

    leads_with_public_link = (
        db.query(func.count(Lead.id))
        .filter(Lead.tenant_id == tenant_id, Lead.public_token.is_not(None))
        .scalar()
        or 0
    )
    last_lead_at = (
        db.query(func.max(Lead.created_at)).filter(Lead.tenant_id == tenant_id).scalar()
    )
    tenant_status = (
        "active"
        if _is_tenant_active(
            subscription_status=tenant.subscription_status,
            trial_ends_at=tenant.trial_ends_at,
            last_lead_at=last_lead_at,
        )
        else "inactive"
    )

    total_leads_i = int(total_leads)
    conversion_pct = (
        round(100.0 * accepted_n / total_leads_i, 1) if total_leads_i else None
    )
    health, health_reason = get_tenant_health(db, tenant_id)

    tenant_summary = {
        "total_leads": total_leads_i,
        "total_estimates": int(total_estimates),
        "plan_code": subscription_info["plan_code"],
        "status": tenant_status,
        "health": health,
        "health_reason": health_reason,
        "leads_with_public_link": int(leads_with_public_link),
        "revenue_total_fmt": _format_eur(rev_total),
        "revenue_30d_fmt": _format_eur(rev_30d),
        "avg_accepted_quote_fmt": _format_eur(avg_accepted) if avg_accepted is not None else "—",
        "accepted_deals": accepted_n,
        "conversion_pct": conversion_pct,
        "leads_30d": int(activity_row.leads_30d or 0),
        "estimates_30d": int(activity_row.estimates_30d or 0),
        "accepted_30d": int(activity_row.accepted_30d or 0),
    }

    return templates.TemplateResponse(
        "founder/tenant_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "tenant": tenant,
            "owner": owner_info,
            "branding": branding,
            "subscription": subscription_info,
            "tenant_summary": tenant_summary,
            "app_public_origin": app_public_origin,
            "recent_quote_rows": recent_quote_rows,
        },
    )
