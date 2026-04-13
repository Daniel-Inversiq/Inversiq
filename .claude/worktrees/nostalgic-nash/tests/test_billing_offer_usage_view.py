from __future__ import annotations

import uuid

from app.models.tenant import Tenant
from app.services.usage_service import get_or_create_usage
from app.services.billing_summary_service import get_billing_offer_usage_view


def _create_tenant(db, *, plan_code: str) -> Tenant:
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Billing Usage Tenant",
        plan_code=plan_code,
        subscription_status="active",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def test_starter_usage_view_under_limit(db) -> None:
    tenant = _create_tenant(db, plan_code="starter_99")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 13
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant)

    assert vm.plan_code == "starter_99"
    assert vm.used_this_month == 13
    assert vm.limit_for_plan == 25
    assert vm.remaining_this_month == 12
    assert vm.unlimited is False
    assert vm.usage_text_nl == "Nog 12 van de 25 offertes over deze maand"
    assert vm.usage_warning_nl is None


def test_starter_usage_view_warns_when_nearly_at_limit(db) -> None:
    tenant = _create_tenant(db, plan_code="starter_99")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 21
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant)

    assert vm.remaining_this_month == 4
    assert vm.usage_warning_nl == (
        "Je zit bijna aan je limiet — upgrade naar Pro voor onbeperkt offertes"
    )


def test_starter_usage_view_reached_limit(db) -> None:
    tenant = _create_tenant(db, plan_code="starter_99")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 25
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant)

    assert vm.remaining_this_month == 0
    assert vm.usage_warning_nl == (
        "Je hebt je limiet bereikt — upgrade naar Pro om door te gaan"
    )


def test_pro_usage_view_unlimited(db) -> None:
    tenant = _create_tenant(db, plan_code="pro_199")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 999
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant)

    assert vm.unlimited is True
    assert vm.limit_for_plan is None
    assert vm.remaining_this_month is None
    assert vm.usage_text_nl == "Onbeperkt offertes"
    assert vm.usage_warning_nl is None


def test_business_usage_view_unlimited(db) -> None:
    tenant = _create_tenant(db, plan_code="business_399")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 999
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant)

    assert vm.unlimited is True
    assert vm.limit_for_plan is None
    assert vm.remaining_this_month is None
    assert vm.usage_text_nl == "Onbeperkt offertes"
    assert vm.usage_warning_nl is None


def test_starter_usage_view_supports_english_language(db) -> None:
    tenant = _create_tenant(db, plan_code="starter_99")
    usage = get_or_create_usage(db, tenant.id)
    usage.quotes_sent = 24
    db.add(usage)
    db.commit()

    vm = get_billing_offer_usage_view(db, tenant, lang="en")

    assert vm.remaining_this_month == 1
    assert vm.usage_text_nl == "1 of 25 quotes remaining this month"
    assert vm.usage_warning_nl == (
        "You are close to your limit - upgrade to Pro for unlimited quotes"
    )
