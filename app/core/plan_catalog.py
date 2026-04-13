from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_PLAN_CODE = "core"
CANONICAL_PLAN_CODES: tuple[str, ...] = (
    "core",
    "growth",
    "pro",
    "scale",
)

# Backwards-compatible aliases for historic/external inputs.
PLAN_CODE_ALIASES: dict[str, str] = {
    # legacy plan codes
    "starter_99": "core",
    "starter": "core",
    "starter_monthly": "core",
    "starter-yearly": "core",
    "pro_199": "growth",
    "business_399": "pro",
    "business": "pro",
}


@dataclass(frozen=True, slots=True)
class PlanCatalogItem:
    code: str
    name: str
    price_cents: int | None          # None = custom/contact sales
    price_display: str
    price_period: str
    quote_limit_label: str
    monthly_request_limit: int | None  # None = unlimited
    tagline_nl: str
    ui_features: tuple[str, ...]
    entitlement_features: frozenset[str]
    stripe_price_env_key: str
    # Founding pricing: applies to core only
    founding_price_cents: int | None = field(default=None)
    founding_stripe_price_env_key: str | None = field(default=None)
    # Top-up pricing (€30 per 10 requests, active subscription required)
    topup_price_cents: int = field(default=3000)
    topup_requests: int = field(default=10)


PLAN_CATALOG: dict[str, PlanCatalogItem] = {
    "core": PlanCatalogItem(
        code="core",
        name="Core",
        price_cents=39900,
        price_display="€399",
        price_period="per maand",
        quote_limit_label="30 aanvragen / maand",
        monthly_request_limit=30,
        tagline_nl="Lage drempel · snelle adoptie",
        ui_features=(
            "30 aanvragen / maand",
            "1 workflow",
            "Standaard rules",
            "Standaard output",
            "+ €30 per 10 extra aanvragen",
        ),
        entitlement_features=frozenset(
            {
                "BASIC_SENDING",
                "TOPUP",
            }
        ),
        stripe_price_env_key="STRIPE_PRICE_CORE",
        founding_price_cents=19900,
        founding_stripe_price_env_key="STRIPE_PRICE_CORE_FOUNDING",
    ),
    "growth": PlanCatalogItem(
        code="growth",
        name="Growth",
        price_cents=89900,
        price_display="€899",
        price_period="per maand",
        quote_limit_label="150 aanvragen / maand",
        monthly_request_limit=150,
        tagline_nl="Core business — hier wil je iedereen",
        ui_features=(
            "150 aanvragen / maand",
            "1–2 workflows",
            "Advanced rules",
            "Automation",
        ),
        entitlement_features=frozenset(
            {
                "BASIC_SENDING",
                "SMART_PRICING",
                "AUTOMATION",
                "TOPUP",
            }
        ),
        stripe_price_env_key="STRIPE_PRICE_GROWTH",
    ),
    "pro": PlanCatalogItem(
        code="pro",
        name="Pro",
        price_cents=249900,
        price_display="€2.499",
        price_period="per maand",
        quote_limit_label="750 aanvragen / maand",
        monthly_request_limit=750,
        tagline_nl="Hoge marge · grotere bedrijven",
        ui_features=(
            "750 aanvragen / maand",
            "Meerdere workflows",
            "Complexe logic",
            "Integraties",
        ),
        entitlement_features=frozenset(
            {
                "BASIC_SENDING",
                "SMART_PRICING",
                "AUTOMATION",
                "CUSTOM_INTEGRATIONS",
                "TOPUP",
            }
        ),
        stripe_price_env_key="STRIPE_PRICE_PRO",
    ),
    "scale": PlanCatalogItem(
        code="scale",
        name="Scale",
        price_cents=None,
        price_display="Op aanvraag",
        price_period="per maand",
        quote_limit_label="Onbeperkt volume",
        monthly_request_limit=None,
        tagline_nl="Enterprise · insurance · logistiek",
        ui_features=(
            "Onbeperkt volume",
            "Custom rules",
            "API / infra",
            "SLA + support",
        ),
        entitlement_features=frozenset(
            {
                "BASIC_SENDING",
                "SMART_PRICING",
                "AUTOMATION",
                "CUSTOM_INTEGRATIONS",
                "DEDICATED_SLA",
                "PRIORITY_SUPPORT",
                "TOPUP",
            }
        ),
        stripe_price_env_key="STRIPE_PRICE_SCALE",
    ),
}

# Top-up product: €30 per 10 requests, only available with active subscription
TOPUP_PRICE_CENTS = 3000
TOPUP_REQUEST_COUNT = 10
TOPUP_STRIPE_PRICE_ENV_KEY = "STRIPE_PRICE_TOPUP"

# Trial defaults
TRIAL_DAYS = 14
TRIAL_REQUEST_LIMIT = 10
TRIAL_DEFAULT_PLAN_CODE = "core"


def resolve_plan_code(plan_code: str | None, *, allow_aliases: bool = True) -> str | None:
    code = (plan_code or "").strip()
    if not code:
        return DEFAULT_PLAN_CODE
    if code in PLAN_CATALOG:
        return code
    if allow_aliases:
        return PLAN_CODE_ALIASES.get(code.lower())
    return None


def get_plan_item(plan_code: str | None, *, allow_aliases: bool = True) -> PlanCatalogItem | None:
    resolved = resolve_plan_code(plan_code, allow_aliases=allow_aliases)
    if not resolved:
        return None
    return PLAN_CATALOG.get(resolved)


def get_stripe_price_id(plan_code: str | None) -> tuple[str | None, str | None]:
    item = get_plan_item(plan_code, allow_aliases=True)
    if not item:
        return None, None
    return item.code, (os.getenv(item.stripe_price_env_key) or "").strip() or None


def get_founding_stripe_price_id(plan_code: str | None) -> tuple[str | None, str | None]:
    """Return the founding price Stripe ID for a plan, if configured."""
    item = get_plan_item(plan_code, allow_aliases=True)
    if not item or not item.founding_stripe_price_env_key:
        return None, None
    return item.code, (os.getenv(item.founding_stripe_price_env_key) or "").strip() or None
