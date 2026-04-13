from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.billing.entitlements import Action, EntitlementResult, check_entitlement
from app.billing.features import Feature


@dataclass(frozen=True)
class TenantStub:
    plan_code: str | None
    subscription_status: str | None
    quotes_sent: int | None = None
    monthly_usage_baseline: int | None = None


@pytest.mark.parametrize(
    "plan_code",
    ["starter_99", "pro_199", "business_399"],
)
def test_send_quote_allowed_for_all_tiers_when_subscription_active(plan_code: str) -> None:
    tenant = TenantStub(
        plan_code=plan_code,
        subscription_status="active",
        quotes_sent=5,
        monthly_usage_baseline=10,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert isinstance(res, EntitlementResult)
    assert res.allowed is True
    assert res.reason is None
    assert res.feature == Feature.BASIC_SENDING.value


def test_send_quote_starter_under_limit_allowed() -> None:
    tenant = TenantStub(
        plan_code="starter_99",
        subscription_status="active",
        quotes_sent=24,
        monthly_usage_baseline=None,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is True
    assert res.reason is None
    assert res.usage_limit == 25
    assert res.usage_current == 24


def test_send_quote_starter_at_limit_denied() -> None:
    tenant = TenantStub(
        plan_code="starter_99",
        subscription_status="active",
        quotes_sent=25,
        monthly_usage_baseline=None,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is False
    assert res.reason == "monthly_offer_limit_reached"
    assert res.usage_limit == 25
    assert res.usage_current == 25


def test_send_quote_pro_unlimited_allowed() -> None:
    tenant = TenantStub(
        plan_code="pro_199",
        subscription_status="active",
        quotes_sent=999,
        monthly_usage_baseline=None,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is True
    assert res.reason is None
    assert res.usage_limit is None
    assert res.usage_current == 999


def test_send_quote_business_unlimited_allowed() -> None:
    tenant = TenantStub(
        plan_code="business_399",
        subscription_status="active",
        quotes_sent=999,
        monthly_usage_baseline=None,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is True
    assert res.reason is None
    assert res.usage_limit is None
    assert res.usage_current == 999


@pytest.mark.parametrize(
    "subscription_status",
    ["inactive", "past_due", "canceled", None, ""],
)
def test_send_quote_denied_for_inactive_subscription(subscription_status: str | None) -> None:
    tenant = TenantStub(
        plan_code="pro_199",
        subscription_status=subscription_status,
        quotes_sent=0,
        monthly_usage_baseline=10,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is False
    assert res.reason == "subscription_inactive"


@pytest.mark.parametrize("plan_code", [None, "", "unknown_plan"])
def test_send_quote_defaults_to_starter_for_missing_or_unknown_plan(plan_code: str | None) -> None:
    tenant = TenantStub(
        plan_code=plan_code,
        subscription_status="active",
        quotes_sent=0,
        monthly_usage_baseline=10,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is True
    assert res.reason is None
    assert res.usage_limit == 10


@pytest.mark.parametrize(
    "plan_code, expected_allowed",
    [
        ("starter_99", False),
        ("pro_199", True),
        ("business_399", True),
    ],
)
def test_export_pdf_entitlement(plan_code: str, expected_allowed: bool) -> None:
    tenant = TenantStub(plan_code=plan_code, subscription_status="active")

    res = check_entitlement(tenant, Action.EXPORT_PDF.value)
    assert res.allowed is expected_allowed
    assert res.feature == Feature.PDF_EXPORT.value
    if not expected_allowed:
        assert res.reason in {"subscription_inactive", "feature_not_in_plan"}


@pytest.mark.parametrize(
    "plan_code, expected_allowed",
    [
        ("starter_99", False),
        ("pro_199", True),
        ("business_399", True),
    ],
)
def test_use_branding_entitlement(plan_code: str, expected_allowed: bool) -> None:
    tenant = TenantStub(plan_code=plan_code, subscription_status="active")

    res = check_entitlement(tenant, Action.USE_BRANDING.value)
    assert res.allowed is expected_allowed
    assert res.feature == Feature.BRANDING.value
    if not expected_allowed:
        assert res.reason in {"subscription_inactive", "feature_not_in_plan"}


@pytest.mark.parametrize(
    "plan_code, expected_allowed",
    [
        ("starter_99", False),
        ("pro_199", False),
        ("business_399", True),
    ],
)
def test_use_whitelabel_entitlement(plan_code: str, expected_allowed: bool) -> None:
    tenant = TenantStub(plan_code=plan_code, subscription_status="active")

    res = check_entitlement(tenant, Action.USE_WHITELABEL.value)
    assert res.allowed is expected_allowed
    assert res.feature == Feature.WHITELABEL.value
    if not expected_allowed:
        assert res.reason in {"subscription_inactive", "feature_not_in_plan"}


def test_unknown_action_denied() -> None:
    tenant = TenantStub(plan_code="pro_199", subscription_status="active")

    res = check_entitlement(tenant, "DOES_NOT_EXIST")
    assert res.allowed is False
    assert res.reason == "unknown_action"
    assert res.action == "DOES_NOT_EXIST"

