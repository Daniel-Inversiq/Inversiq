from __future__ import annotations

import json
import uuid

from app.auth.jwt import create_access_token
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.user import User


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_user_and_tenant(db):
    tenant_id = _uid("tenant")
    user_id = _uid("user")
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        subscription_status="active",
        plan_code="pro",
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


def _make_lead(db, *, tenant_id: str, with_estimate: bool) -> Lead:
    lead = Lead(
        tenant_id=tenant_id,
        name="Review Candidate",
        email=f"{_uid('lead')}@example.com",
        status="SUCCEEDED" if with_estimate else "NEW",
        estimate_json=json.dumps({"totals": {"grand_total": 1000}}) if with_estimate else None,
        estimate_html_key="quotes/demo/index.html" if with_estimate else None,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_quote_from_lead_returns_existing_quote_id(client, db):
    user = _seed_user_and_tenant(db)
    lead = _make_lead(db, tenant_id=user.tenant_id, with_estimate=True)

    response = client.post(f"/quotes/from-lead/{lead.id}", headers=_auth_headers_for_user(user))
    assert response.status_code == 200
    body = response.json()
    assert body["quote_id"] == lead.id
    assert body["lead_id"] == lead.id


def test_quote_from_lead_creates_quote_when_missing(client, db, monkeypatch):
    user = _seed_user_and_tenant(db)
    lead = _make_lead(db, tenant_id=user.tenant_id, with_estimate=False)

    def _fake_publish_quote(*, lead_id, background, db, request=None, tenant_id=None):  # noqa: ANN001
        refreshed = db.query(Lead).filter(Lead.id == lead_id).first()
        refreshed.status = "SUCCEEDED"
        refreshed.estimate_json = json.dumps({"totals": {"grand_total": 1200}})
        refreshed.estimate_html_key = "quotes/generated/index.html"
        db.add(refreshed)
        db.commit()
        return None

    monkeypatch.setattr("app.routers.quotes.publish_quote", _fake_publish_quote)

    response = client.post(f"/quotes/from-lead/{lead.id}", headers=_auth_headers_for_user(user))
    assert response.status_code == 200
    body = response.json()
    assert body["quote_id"] == lead.id
    assert body["lead_id"] == lead.id
    assert body["status"] == "SUCCEEDED"


def test_quote_from_lead_rejects_other_tenant_lead(client, db):
    owner = _seed_user_and_tenant(db)
    other = _seed_user_and_tenant(db)
    lead = _make_lead(db, tenant_id=other.tenant_id, with_estimate=True)

    response = client.post(f"/quotes/from-lead/{lead.id}", headers=_auth_headers_for_user(owner))
    assert response.status_code == 404
