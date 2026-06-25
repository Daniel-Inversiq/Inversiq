from __future__ import annotations

from app.models.tenant import Tenant
from app.verticals.registry import VERTICALS, get_vertical

DEFAULT_SECTOR = "construction"

_SECTOR_TO_ADAPTER_KEY: dict[str, str] = {
    "construction": "construction",
}


def normalize_sector(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return DEFAULT_SECTOR
    if normalized in VERTICALS:
        return normalized
    return DEFAULT_SECTOR


def intake_adapter_key_for_tenant(tenant: Tenant) -> str:
    sector = normalize_sector(getattr(tenant, "sector", None))
    return _SECTOR_TO_ADAPTER_KEY.get(sector, DEFAULT_SECTOR)


def get_intake_adapter_for_tenant(tenant: Tenant):
    sector = normalize_sector(getattr(tenant, "sector", None))
    return get_vertical(sector)
