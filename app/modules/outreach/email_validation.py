"""
Lightweight recipient validation for outreach suggestions (syntax + DNS via email-validator).

Uses the same stack as email-validator deliverability checks (MX, then A/AAAA fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from email_validator import (
    EmailNotValidError,
    EmailSyntaxError,
    EmailUndeliverableError,
    validate_email,
)

# Aligned with consumer-mail dedupe in outreach routes.
PUBLIC_MAILBOX_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "icloud.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
    }
)

RESULT_INVALID_EMAIL = "invalid_email"
RESULT_INVALID_DOMAIN = "invalid_domain"
RESULT_VALID_MX = "valid_mx"
RESULT_VALID_FALLBACK_A = "valid_fallback_a"
RESULT_NO_MX = "no_mx"
RESULT_PUBLIC_MAILBOX = "public_mailbox"


@dataclass(frozen=True)
class OutreachEmailValidation:
    """Outcome of validate_recipient_for_outreach."""

    result: str
    normalized_email: str
    normalized_domain: str
    is_deliverability_risky: bool
    validation_reason: str
    should_insert: bool


def _domain_public(domain_lower: str) -> bool:
    return domain_lower in PUBLIC_MAILBOX_DOMAINS


def _domain_from_raw(email: str) -> str:
    parts = email.strip().lower().split("@")
    if len(parts) == 2 and parts[1] and "." in parts[1]:
        return parts[1]
    return ""


def validate_recipient_for_outreach(
    raw_email: str,
    *,
    dns_timeout_seconds: Optional[float] = None,
) -> OutreachEmailValidation:
    """
    Validate syntax and DNS deliverability. Excludes only clearly undeliverable addresses.

    Result labels:
    - invalid_email: RFC-level syntax failure
    - invalid_domain: domain does not exist or has no mail path (NXDOMAIN, null MX, no MX/A/AAAA)
    - valid_mx: MX records present (business domains)
    - valid_fallback_a: no MX but A or AAAA usable as SMTP fallback (risky)
    - no_mx: DNS inconclusive (e.g. timeout / no nameservers) — insert with risk flag
    - public_mailbox: known consumer domain (gmail, etc.); still checked for DNS where possible
    """
    timeout = int(dns_timeout_seconds) if dns_timeout_seconds is not None else None

    try:
        v = validate_email(
            (raw_email or "").strip(),
            check_deliverability=True,
            timeout=timeout,
        )
    except EmailSyntaxError as e:
        raw = (raw_email or "").strip()
        return OutreachEmailValidation(
            result=RESULT_INVALID_EMAIL,
            normalized_email=raw.lower(),
            normalized_domain=_domain_from_raw(raw),
            is_deliverability_risky=False,
            validation_reason=str(e),
            should_insert=False,
        )
    except EmailUndeliverableError as e:
        raw = (raw_email or "").strip()
        return OutreachEmailValidation(
            result=RESULT_INVALID_DOMAIN,
            normalized_email=raw.lower(),
            normalized_domain=_domain_from_raw(raw),
            is_deliverability_risky=False,
            validation_reason=str(e),
            should_insert=False,
        )
    except EmailNotValidError as e:
        raw = (raw_email or "").strip()
        return OutreachEmailValidation(
            result=RESULT_INVALID_EMAIL,
            normalized_email=raw.lower(),
            normalized_domain=_domain_from_raw(raw),
            is_deliverability_risky=False,
            validation_reason=str(e),
            should_insert=False,
        )

    normalized = (v.normalized or "").strip()
    domain_l = (v.ascii_domain or "").lower()
    mx_records = getattr(v, "mx", None)
    fb = getattr(v, "mx_fallback_type", None)

    # Unknown deliverability (timeout / no nameservers): library returns without mx info.
    if not mx_records and fb is None:
        reason = (
            "DNS deliverability check did not return MX or A/AAAA fallback "
            "(resolver timeout or inconclusive); not treated as hard-fail."
        )
        risky = True
        result = RESULT_NO_MX
        if _domain_public(domain_l):
            result = RESULT_PUBLIC_MAILBOX
            reason = (
                "Consumer mailbox domain; " + reason
            )
        return OutreachEmailValidation(
            result=result,
            normalized_email=normalized.lower(),
            normalized_domain=domain_l,
            is_deliverability_risky=risky,
            validation_reason=reason,
            should_insert=True,
        )

    if fb in ("A", "AAAA"):
        base_reason = (
            f"No MX records; SMTP may use {fb} record fallback (deprecated but still seen in the wild)."
        )
        risky = True
        result = RESULT_VALID_FALLBACK_A
        if _domain_public(domain_l):
            result = RESULT_PUBLIC_MAILBOX
            reason = f"Consumer mailbox ({domain_l}); {base_reason}"
        else:
            reason = base_reason
        return OutreachEmailValidation(
            result=result,
            normalized_email=normalized.lower(),
            normalized_domain=domain_l,
            is_deliverability_risky=risky,
            validation_reason=reason,
            should_insert=True,
        )

    # True MX records present
    base_reason = "MX records found for domain."
    risky = False
    result = RESULT_VALID_MX
    if _domain_public(domain_l):
        result = RESULT_PUBLIC_MAILBOX
        risky = True
        reason = f"Consumer mailbox ({domain_l}); {base_reason}"
    else:
        reason = base_reason

    return OutreachEmailValidation(
        result=result,
        normalized_email=normalized.lower(),
        normalized_domain=domain_l,
        is_deliverability_risky=risky,
        validation_reason=reason,
        should_insert=True,
    )
