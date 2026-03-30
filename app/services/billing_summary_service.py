from typing import Any, Dict

from sqlalchemy.orm import Session

from app.services.usage_service import get_or_create_usage


PLAN_LABELS: Dict[str, str] = {
    "starter_99": "Starter",
    "pro_199": "Pro",
    "business_399": "Business",
}


def get_billing_usage_summary(db: Session, tenant: Any) -> Dict[str, Any]:
    """
    Return a summary of billing usage for a tenant.
    """
    plan_key = tenant.plan_code or "starter_99"
    plan_label = PLAN_LABELS.get(plan_key, plan_key)

    usage = get_or_create_usage(db, str(tenant.id))
    quotes_sent = usage.quotes_sent or 0

    return {
        "plan_code": plan_key,
        "plan_label": plan_label,
        "quotes_sent": quotes_sent,
        # Explicit analytics semantics: this is tracking, not gating.
        "monthly_quotes_sent": quotes_sent,
        "usage_tracking_enabled": True,
    }

