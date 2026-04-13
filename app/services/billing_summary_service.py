from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Protocol

from sqlalchemy.orm import Session

from app.core.plan_catalog import DEFAULT_PLAN_CODE, get_plan_item, resolve_plan_code
from app.i18n.service import translate
from app.services.usage_service import get_or_create_usage


PLAN_LABELS: Dict[str, str] = {
    "core": "Core",
    "growth": "Growth",
    "pro": "Pro",
    "scale": "Scale",
}


class TenantLike(Protocol):
    id: str
    plan_code: str | None


@dataclass(frozen=True, slots=True)
class BillingOfferUsageView:
    plan_code: str
    used_this_month: int
    limit_for_plan: int | None
    remaining_this_month: int | None
    unlimited: bool
    usage_text_nl: str
    usage_warning_nl: str | None


def get_billing_offer_usage_view(
    db: Session,
    tenant: TenantLike,
    lang: str = "nl",
) -> BillingOfferUsageView:
    resolved_plan_code = resolve_plan_code(getattr(tenant, "plan_code", None)) or DEFAULT_PLAN_CODE
    plan_item = get_plan_item(resolved_plan_code) or get_plan_item(DEFAULT_PLAN_CODE)
    limit_for_plan = None if plan_item is None else plan_item.monthly_request_limit

    usage = get_or_create_usage(db, str(tenant.id))
    used_this_month = int(getattr(usage, "quotes_sent", 0) or 0)

    unlimited = limit_for_plan is None
    if unlimited:
        return BillingOfferUsageView(
            plan_code=resolved_plan_code,
            used_this_month=used_this_month,
            limit_for_plan=None,
            remaining_this_month=None,
            unlimited=True,
            usage_text_nl=translate("billing.usage_unlimited", lang=lang),
            usage_warning_nl=None,
        )

    remaining = max(int(limit_for_plan) - used_this_month, 0)
    usage_text_nl = translate(
        "billing.remaining_offers",
        lang=lang,
        remaining=remaining,
        limit=limit_for_plan,
    )

    warning: str | None = None
    if remaining == 0:
        warning = translate("billing.limit_reached_warning", lang=lang)
    elif remaining <= 5:
        warning = translate("billing.limit_near_warning", lang=lang)

    return BillingOfferUsageView(
        plan_code=resolved_plan_code,
        used_this_month=used_this_month,
        limit_for_plan=int(limit_for_plan),
        remaining_this_month=remaining,
        unlimited=False,
        usage_text_nl=usage_text_nl,
        usage_warning_nl=warning,
    )


def get_billing_usage_summary(db: Session, tenant: Any) -> Dict[str, Any]:
    """
    Return a summary of billing usage for a tenant.
    """
    plan_key = resolve_plan_code(getattr(tenant, "plan_code", None)) or DEFAULT_PLAN_CODE
    plan_label = PLAN_LABELS.get(plan_key, plan_key)

    usage_view = get_billing_offer_usage_view(db, tenant)
    quotes_sent = usage_view.used_this_month

    return {
        "plan_code": usage_view.plan_code,
        "plan_label": plan_label,
        "quotes_sent": quotes_sent,
        # Explicit analytics semantics: this is tracking, not gating.
        "monthly_quotes_sent": quotes_sent,
        "usage_tracking_enabled": True,
        "offer_usage_view": asdict(usage_view),
    }

