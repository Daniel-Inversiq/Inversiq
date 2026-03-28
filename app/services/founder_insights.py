from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.lead import Lead


def _last_activity_timestamp(
    max_created: datetime | None,
    max_updated: datetime | None,
    max_sent: datetime | None,
) -> datetime | None:
    """Most recent signal: new lead, estimate/workflow update, or quote sent."""
    candidates = [d for d in (max_created, max_updated, max_sent) if d is not None]
    return max(candidates) if candidates else None


def _to_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _days_since(last: datetime | None, now: datetime) -> int:
    if last is None:
        return 0
    return max(0, int((_to_utc_aware(now) - _to_utc_aware(last)).total_seconds() // 86400))


def get_tenant_health(db: Session, tenant_id: str) -> tuple[str, str]:
    """
    Derive a coarse health label for founder-facing views.

    Returns (health, reason) where health is "healthy", "warning", or "at_risk".
    Uses last activity = max(created_at, updated_at, sent_at) per tenant.
    """
    now = datetime.now(timezone.utc)
    cutoff_14d = now - timedelta(days=14)
    cutoff_30d = now - timedelta(days=30)

    row = (
        db.query(
            func.count(Lead.id).label("total_leads"),
            func.coalesce(
                func.sum(case((Lead.created_at >= cutoff_14d, 1), else_=0)), 0
            ).label("leads_14d"),
            func.coalesce(
                func.sum(case((Lead.created_at >= cutoff_30d, 1), else_=0)), 0
            ).label("leads_30d"),
            func.coalesce(
                func.sum(case((Lead.accepted_at >= cutoff_30d, 1), else_=0)), 0
            ).label("accepted_30d"),
            func.coalesce(
                func.sum(case((Lead.accepted_at.is_not(None), 1), else_=0)), 0
            ).label("accepted"),
            func.max(Lead.created_at).label("max_created"),
            func.max(Lead.updated_at).label("max_updated"),
            func.max(Lead.sent_at).label("max_sent"),
        )
        .filter(Lead.tenant_id == tenant_id)
        .one()
    )

    total_leads = int(row.total_leads or 0)
    leads_14d = int(row.leads_14d or 0)
    leads_30d = int(row.leads_30d or 0)
    accepted_30d = int(row.accepted_30d or 0)
    accepted = int(row.accepted or 0)

    last_activity = _last_activity_timestamp(
        row.max_created,
        row.max_updated,
        row.max_sent,
    )

    if total_leads == 0 or last_activity is None:
        return ("at_risk", "No leads or activity recorded yet")

    if _to_utc_aware(last_activity) < cutoff_14d:
        days = _days_since(last_activity, now)
        return ("at_risk", f"No activity for {days} days")

    if leads_30d >= 10 and accepted_30d == 0:
        return ("at_risk", "High leads but 0 conversions in last 30 days")

    if total_leads > 20 and accepted == 0:
        return ("at_risk", "High lead volume but no conversions yet")

    if leads_14d < 5:
        lead_phrase = (
            "1 new lead in last 14 days"
            if leads_14d == 1
            else f"{leads_14d} new leads in last 14 days"
        )
        return ("warning", f"Low activity — only {lead_phrase}")

    if total_leads > 0 and (accepted / total_leads) < 0.10:
        pct = round(100.0 * accepted / total_leads, 1)
        return ("warning", f"Low conversion — {pct}% accepted ({accepted}/{total_leads} leads)")

    return ("healthy", "Performing well")
