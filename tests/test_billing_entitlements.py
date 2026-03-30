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


@pytest.mark.parametrize(
    "plan_code, quotes_sent, monthly_usage_baseline",
    [
        ("starter_99", 10, 10),
        ("pro_199", 10, 10),
        ("business_399", 10, 10),
        ("starter_99", 25, 10),
        ("pro_199", 25, 10),
        ("business_399", 25, 10),
    ],
)
def test_send_quote_not_blocked_by_usage_across_tiers(
    plan_code: str, quotes_sent: int, monthly_usage_baseline: int
) -> None:
    tenant = TenantStub(
        plan_code=plan_code,
        subscription_status="active",
        quotes_sent=quotes_sent,
        monthly_usage_baseline=monthly_usage_baseline,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is True
    assert res.reason is None
    # Usage counters are still surfaced for analytics / monitoring.
    assert res.usage_limit == monthly_usage_baseline
    assert res.usage_current == quotes_sent


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


def test_send_quote_allowed_when_usage_limit_reached_but_ignored() -> None:
    tenant = TenantStub(
        plan_code="pro_199",
        subscription_status="active",
        quotes_sent=10,
        monthly_usage_baseline=10,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    # Usage counters are still captured, but monthly offer caps are no longer enforced.
    assert res.allowed is True
    assert res.reason is None
    assert res.usage_limit == 10
    assert res.usage_current == 10


@pytest.mark.parametrize("plan_code", [None, "", "unknown_plan"])
def test_send_quote_denied_for_unknown_or_none_plan(plan_code: str | None) -> None:
    tenant = TenantStub(
        plan_code=plan_code,
        subscription_status="active",
        quotes_sent=0,
        monthly_usage_baseline=10,
    )

    res = check_entitlement(tenant, Action.SEND_QUOTE.value)
    assert res.allowed is False
    assert res.reason == "feature_not_in_plan"
    assert res.feature == Feature.BASIC_SENDING.value


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

