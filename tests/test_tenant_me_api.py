from __future__ import annotations

import uuid

import pytest

from app.auth.jwt import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_user_and_tenant(db, *, sector: str = "construction") -> User:
    tenant_id = _uid("tenant")
    user_id = _uid("user")
    tenant = Tenant(
        id=tenant_id,
        name="Tenant Me API",
        sector=sector,
    )
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.com",
        password_hash="not-used-in-tests",
        is_active=True,
    )
    db.add(tenant)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers_for_user(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


def _assert_vertical_shape(body: dict) -> None:
    assert "vertical" in body
    vertical = body["vertical"]
    assert "key" in vertical
    assert "label" in vertical
    assert "workflows" in vertical
    assert "ui_workflows" in vertical
    assert "engine_pipeline" in vertical
    assert "features" in vertical
    assert "dashboard" in vertical
    assert isinstance(vertical["workflows"], list)
    assert isinstance(vertical["ui_workflows"], list)
    assert isinstance(vertical["engine_pipeline"], list)
    assert isinstance(vertical["features"], dict)
    assert isinstance(vertical["dashboard"], dict)


def test_tenant_me_returns_expected_shape(client, db):
    user = _seed_user_and_tenant(db, sector="construction")
    response = client.get("/api/tenant/me", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.tenant_id
    assert body["sector"] == "construction"
    _assert_vertical_shape(body)


@pytest.mark.parametrize("sector", ["construction", "roofing", "solar"])
def test_patch_tenant_sector_updates_sector_and_returns_tenant_shape(client, db, sector):
    user = _seed_user_and_tenant(db, sector="construction")
    response = client.patch(
        "/api/tenant/sector",
        json={"sector": sector},
        headers=_auth_headers_for_user(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.tenant_id
    assert body["sector"] == sector
    _assert_vertical_shape(body)

    updated_tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    assert updated_tenant is not None
    assert updated_tenant.sector == sector
    if hasattr(updated_tenant, "onboarding_completed"):
        assert bool(getattr(updated_tenant, "onboarding_completed")) is True
        assert body["onboarding_completed"] is True


def test_patch_tenant_sector_rejects_invalid_sector(client, db):
    user = _seed_user_and_tenant(db, sector="construction")
    response = client.patch(
        "/api/tenant/sector",
        json={"sector": "invalid-sector"},
        headers=_auth_headers_for_user(user),
    )

    assert response.status_code == 400


def test_patch_tenant_sector_requires_auth(client):
    response = client.patch("/api/tenant/sector", json={"sector": "solar"})
    assert response.status_code == 401
