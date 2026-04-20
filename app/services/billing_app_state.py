"""
Shared billing page state for the Jinja billing page and the JSON API used by the Next.js shell.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.plan_catalog import (
    CANONICAL_PLAN_CODES,
    DEFAULT_PLAN_CODE,
    PLAN_CATALOG,
    get_plan_item,
)
from app.i18n.service import translate
from app.models.tenant import Tenant
from app.services.billing_summary_service import (
    BillingOfferUsageView,
    get_billing_offer_usage_view,
)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


@dataclass(frozen=True, slots=True)
class BillingPlanRow:
    code: str
    name: str
    price_display: str
    price_period: str
    quote_limit_label: str
    features: list[str]
    tagline: str
    is_recommended: bool
    cta_label: str


@dataclass(frozen=True, slots=True)
class BillingPageState:
    title: str
    plans: list[BillingPlanRow]
    current_plan_code: str
    current_plan_name: str
    current_plan_price_label: str
    subscription_status: str
    subscription_status_label: str
    trial_ends_at: datetime | None
    trial_days_left: int | None
    trial_ends_at_display: str | None
    is_paid_or_trialing: bool
    billing_status_error: bool
    portal_error_no_customer: bool
    billing_offer_usage: BillingOfferUsageView | None


_plan_i18n_keys = {
    "core": "core",
    "growth": "growth",
    "pro": "pro",
    "scale": "scale",
}

_plan_cta_keys = {
    "core": "billing.cta.choose_core",
    "growth": "billing.cta.choose_growth",
    "pro": "billing.cta.choose_pro",
    "scale": "billing.cta.choose_scale",
}


def compute_billing_page_state(
    *,
    db: Session,
    tenant: Tenant | None,
    request_lang: str,
    billing_status_error: bool,
    portal_error_no_customer: bool,
) -> BillingPageState:
    if tenant is None:
        return _billing_state_without_tenant_row(
            request_lang=request_lang,
            billing_status_error=billing_status_error,
            portal_error_no_customer=portal_error_no_customer,
        )

    current_plan_code = getattr(tenant, "plan_code", None) or DEFAULT_PLAN_CODE

    subscription_status = getattr(tenant, "subscription_status", None) or "inactive"

    trial_ends_at = getattr(tenant, "trial_ends_at", None)
    trial_days_left: int | None
    if not trial_ends_at:
        trial_days_left = None
    else:
        te = trial_ends_at
        if getattr(te, "tzinfo", None) is None:
            te = te.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = te - now
        trial_days_left = max(int(delta.days), 0)

    is_paid_or_trialing = subscription_status in ("trialing", "active")

    current_plan_item = get_plan_item(current_plan_code) or PLAN_CATALOG[DEFAULT_PLAN_CODE]
    current_plan_i18n_key = _plan_i18n_keys.get(current_plan_item.code, current_plan_item.code)
    current_plan_name = translate(
        f"billing.plan.{current_plan_i18n_key}.name",
        lang=request_lang,
    )
    current_plan_price_label = (
        f"{current_plan_item.price_display} {translate('billing.price_period_monthly', lang=request_lang)}".strip()
    )

    billing_offer_usage = get_billing_offer_usage_view(db, tenant, lang=request_lang)

    trial_ends_at_display: str | None = None
    if trial_ends_at is not None:
        te = trial_ends_at
        if getattr(te, "tzinfo", None) is None:
            te = te.replace(tzinfo=timezone.utc)
        trial_ends_at_display = te.astimezone(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y")

    subscription_status_label = {
        "trialing": translate("billing.status.trialing", lang=request_lang),
        "active": translate("billing.status.active", lang=request_lang),
        "inactive": translate("billing.status.inactive", lang=request_lang),
        "past_due": translate("billing.status.past_due", lang=request_lang),
        "canceled": translate("billing.status.canceled", lang=request_lang),
        "unpaid": translate("billing.status.unpaid", lang=request_lang),
    }.get(
        subscription_status,
        subscription_status.replace("_", " ").title(),
    )

    plans: list[BillingPlanRow] = []
    for item in (PLAN_CATALOG[c] for c in CANONICAL_PLAN_CODES):
        code = item.code
        i18n_key = _plan_i18n_keys.get(code, code)
        plans.append(
            BillingPlanRow(
                code=code,
                name=translate(f"billing.plan.{i18n_key}.name", lang=request_lang),
                price_display=item.price_display,
                price_period=translate("billing.price_period_monthly", lang=request_lang),
                quote_limit_label=translate(
                    f"billing.plan.{i18n_key}.limit_label",
                    lang=request_lang,
                ),
                features=[
                    translate(
                        f"billing.plan.{i18n_key}.features.f1",
                        lang=request_lang,
                    ),
                    translate(
                        f"billing.plan.{i18n_key}.features.f2",
                        lang=request_lang,
                    ),
                    translate(
                        f"billing.plan.{i18n_key}.features.f3",
                        lang=request_lang,
                    ),
                ],
                tagline=translate(f"billing.plan.{i18n_key}.subtitle", lang=request_lang),
                is_recommended=code == "growth",
                cta_label=translate(
                    _plan_cta_keys.get(code, "billing.cta.choose_plan"),
                    lang=request_lang,
                ),
            )
        )

    return BillingPageState(
        title=translate("billing.title", lang=request_lang),
        plans=plans,
        current_plan_code=current_plan_code,
        current_plan_name=current_plan_name,
        current_plan_price_label=current_plan_price_label,
        subscription_status=subscription_status,
        subscription_status_label=subscription_status_label,
        trial_ends_at=trial_ends_at,
        trial_days_left=trial_days_left,
        trial_ends_at_display=trial_ends_at_display,
        is_paid_or_trialing=is_paid_or_trialing,
        billing_status_error=billing_status_error,
        portal_error_no_customer=portal_error_no_customer,
        billing_offer_usage=billing_offer_usage,
    )


def _billing_state_without_tenant_row(
    *,
    request_lang: str,
    billing_status_error: bool,
    portal_error_no_customer: bool,
) -> BillingPageState:
    """Parity with legacy /app/billing when no Tenant row exists."""
    subscription_status = "inactive"
    subscription_status_label = translate("billing.status.inactive", lang=request_lang)
    plans: list[BillingPlanRow] = []
    for item in (PLAN_CATALOG[c] for c in CANONICAL_PLAN_CODES):
        code = item.code
        i18n_key = _plan_i18n_keys.get(code, code)
        plans.append(
            BillingPlanRow(
                code=code,
                name=translate(f"billing.plan.{i18n_key}.name", lang=request_lang),
                price_display=item.price_display,
                price_period=translate("billing.price_period_monthly", lang=request_lang),
                quote_limit_label=translate(
                    f"billing.plan.{i18n_key}.limit_label",
                    lang=request_lang,
                ),
                features=[
                    translate(
                        f"billing.plan.{i18n_key}.features.f1",
                        lang=request_lang,
                    ),
                    translate(
                        f"billing.plan.{i18n_key}.features.f2",
                        lang=request_lang,
                    ),
                    translate(
                        f"billing.plan.{i18n_key}.features.f3",
                        lang=request_lang,
                    ),
                ],
                tagline=translate(f"billing.plan.{i18n_key}.subtitle", lang=request_lang),
                is_recommended=code == "growth",
                cta_label=translate(
                    _plan_cta_keys.get(code, "billing.cta.choose_plan"),
                    lang=request_lang,
                ),
            )
        )
    current_plan_item = get_plan_item(DEFAULT_PLAN_CODE) or PLAN_CATALOG[DEFAULT_PLAN_CODE]
    current_plan_i18n_key = _plan_i18n_keys.get(current_plan_item.code, current_plan_item.code)
    current_plan_name = translate(
        f"billing.plan.{current_plan_i18n_key}.name",
        lang=request_lang,
    )
    current_plan_price_label = (
        f"{current_plan_item.price_display} {translate('billing.price_period_monthly', lang=request_lang)}".strip()
    )
    return BillingPageState(
        title=translate("billing.title", lang=request_lang),
        plans=plans,
        current_plan_code=DEFAULT_PLAN_CODE,
        current_plan_name=current_plan_name,
        current_plan_price_label=current_plan_price_label,
        subscription_status=subscription_status,
        subscription_status_label=subscription_status_label,
        trial_ends_at=None,
        trial_days_left=None,
        trial_ends_at_display=None,
        is_paid_or_trialing=False,
        billing_status_error=billing_status_error,
        portal_error_no_customer=portal_error_no_customer,
        billing_offer_usage=None,
    )


def billing_page_state_to_template_context(state: BillingPageState) -> dict[str, Any]:
    """Context keys expected by app/billing.html."""
    return {
        "title": state.title,
        "plans": [asdict(p) for p in state.plans],
        "current_plan_code": state.current_plan_code,
        "current_plan_name": state.current_plan_name,
        "current_plan_price_label": state.current_plan_price_label,
        "subscription_status": state.subscription_status,
        "subscription_status_label": state.subscription_status_label,
        "trial_ends_at": state.trial_ends_at,
        "trial_ends_at_display": state.trial_ends_at_display,
        "trial_days_left": state.trial_days_left,
        "is_paid_or_trialing": state.is_paid_or_trialing,
        "billing_status_error": state.billing_status_error,
        "portal_error_no_customer": state.portal_error_no_customer,
        "billing_offer_usage": state.billing_offer_usage,
    }


def billing_page_state_to_api_payload(state: BillingPageState) -> dict[str, Any]:
    """JSON-serializable dict for GET /app/api/billing."""
    usage = state.billing_offer_usage
    return {
        "title": state.title,
        "plans": [asdict(p) for p in state.plans],
        "current_plan_code": state.current_plan_code,
        "current_plan_name": state.current_plan_name,
        "current_plan_price_label": state.current_plan_price_label,
        "subscription_status": state.subscription_status,
        "subscription_status_label": state.subscription_status_label,
        "trial_days_left": state.trial_days_left,
        "trial_ends_at_display": state.trial_ends_at_display,
        "trial_ends_at_iso": _iso_utc(state.trial_ends_at),
        "is_paid_or_trialing": state.is_paid_or_trialing,
        "billing_status_error": state.billing_status_error,
        "portal_error_no_customer": state.portal_error_no_customer,
        "billing_offer_usage": None if usage is None else asdict(usage),
    }
