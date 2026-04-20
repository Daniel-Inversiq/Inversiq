"""
Absolute return URLs for Stripe and billing-related redirects.

When APP_SHELL_PUBLIC_BASE_URL is set (e.g. the Next.js app origin), paths use /billing
so users return to the embedded shell instead of legacy /app/billing HTML.
"""

from __future__ import annotations

import os

from fastapi import Request

from app.core.settings import settings


def _shell_base_configured() -> bool:
    return bool(
        (getattr(settings, "APP_SHELL_PUBLIC_BASE_URL", "") or os.getenv("APP_SHELL_PUBLIC_BASE_URL") or "").strip()
    )


def billing_app_path() -> str:
    return "/billing" if _shell_base_configured() else "/app/billing"


def billing_public_base(request: Request) -> str:
    shell = (getattr(settings, "APP_SHELL_PUBLIC_BASE_URL", "") or os.getenv("APP_SHELL_PUBLIC_BASE_URL") or "").strip()
    if shell:
        return shell.rstrip("/")
    return (
        os.getenv("APP_BASE_URL") or settings.APP_PUBLIC_BASE_URL or str(request.base_url)
    ).rstrip("/")


def billing_return_url(request: Request, query: str = "") -> str:
    """
    Absolute URL for post-checkout / portal return (Stripe success_url, cancel_url, portal return_url).
    Query should not include a leading "?".
    """
    base = billing_public_base(request)
    path = billing_app_path()
    q = f"?{query}" if query else ""
    return f"{base}{path}{q}"
