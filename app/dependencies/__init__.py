"""Shared FastAPI dependency modules."""

from app.dependencies.common import (
    get_s3_service,
    get_storage_service,
    get_tenant_settings,
    get_tenant_storage_path,
    resolve_tenant,
    tenant_service,
)

__all__ = [
    "get_s3_service",
    "get_storage_service",
    "get_tenant_settings",
    "get_tenant_storage_path",
    "resolve_tenant",
    "tenant_service",
]
