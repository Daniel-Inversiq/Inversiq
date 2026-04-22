from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Lead, Tenant


@dataclass
class QuoteReadinessResult:
    is_ready: bool
    missing_config: list[str]


def validate_quote_readiness(lead: Lead, tenant: Tenant | None) -> QuoteReadinessResult:
    """
    Validate tenant-level quote configuration required for price generation.

    This check must not influence intake/review classification.
    """
    _ = lead  # reserved for future lead-specific checks
    pricing = dict(getattr(tenant, "pricing_json", {}) or {}) if tenant is not None else {}
    missing_config: list[str] = []

    price_per_m2 = pricing.get("price_per_m2", pricing.get("walls_rate_eur_per_sqm"))
    if price_per_m2 in (None, ""):
        missing_config.append("price_per_m2")

    return QuoteReadinessResult(
        is_ready=(len(missing_config) == 0),
        missing_config=missing_config,
    )


def validateQuoteReadiness(lead: Lead, tenant: Tenant | None) -> QuoteReadinessResult:
    """Compatibility alias matching requested naming."""
    return validate_quote_readiness(lead, tenant)


def readiness_payload(result: QuoteReadinessResult) -> dict[str, Any]:
    return {
        "isReady": bool(result.is_ready),
        "missingConfig": list(result.missing_config),
        "missing_pricing_config": not result.is_ready,
    }
