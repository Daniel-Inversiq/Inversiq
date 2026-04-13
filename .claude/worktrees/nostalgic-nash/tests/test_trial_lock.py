import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.models.lead import Lead
from app.auth.passwords import hash_password


def _create_test_tenant_user_lead(db: Session) -> tuple[Tenant, User, Lead, str]:
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        company_name="Test Tenant",
        email="test-tenant@example.com",
        slug=f"test-tenant-{tenant_id[:8]}",
        plan_code="pro_199",
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        pricing_json={"walls_rate_eur_per_sqm": 10.0},
    )

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"user-{user_id[:8]}@example.com",
        password_hash=hash_password("testpassword"),
        is_active=True,
        is_platform_admin=False,
    )

    lead = Lead(
        id=lead_id,
        tenant_id=tenant_id,
        name="Test Lead",
        email="customer@example.com",
    )

    db.add(tenant)
    db.add(user)
    db.add(lead)
    db.commit()
    db.refresh(tenant)
    db.refresh(user)
    db.refresh(lead)

    return tenant, user, lead, "testpassword"


def _expire_trial_for_tenant(db: Session, tenant: Tenant) -> None:
    tenant.subscription_status = "trialing"
    tenant.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)


def _expired_trial_context(client: TestClient, db: Session) -> dict:
    """
    Maakt tenant/user/lead in de test-DB, expiret de trial
    en logt in met dezelfde TestClient.
    """
    tenant, user, lead, password = _create_test_tenant_user_lead(db)
    _expire_trial_for_tenant(db, tenant)

    resp = client.post(
        "/auth/login",
        data={"email": user.email, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    return {
        "tenant": tenant,
        "user": user,
        "lead": lead,
    }


def test_uploads_presign_blocked_for_expired_trial(client: TestClient, db: Session):
    ctx = _expired_trial_context(client, db)
    lead = ctx["lead"]

    resp = client.post(
        "/uploads/presign",
        json={
            "filename": "photo.jpg",
            "lead_id": str(lead.id),
            "content_type": "image/jpeg",
            "size": 1024,
        },
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "subscription_inactive"}


def test_quotes_publish_blocked_for_expired_trial(client: TestClient, db: Session):
    ctx = _expired_trial_context(client, db)
    lead = ctx["lead"]

    resp = client.post(f"/quotes/publish/{lead.id}")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "subscription_inactive"}


def test_reviews_generate_estimate_redirect_for_expired_trial(
    client: TestClient, db: Session
):
    ctx = _expired_trial_context(client, db)
    lead = ctx["lead"]

    resp = client.post(
        f"/app/reviews/{lead.id}/generate-estimate",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers.get("Location") or resp.headers.get("location")
    assert location == "/app/billing"


def test_lead_detail_still_accessible_in_read_only_mode(
    client: TestClient, db: Session
):
    ctx = _expired_trial_context(client, db)
    lead = ctx["lead"]

    resp = client.get(
        f"/app/leads/{lead.id}",
        headers={"Accept": "text/html"},
    )
    assert resp.status_code == 200
    assert str(lead.id) in resp.text


def test_billing_page_accessible_for_expired_trial(client: TestClient, db: Session):
    _ = _expired_trial_context(client, db)

    resp = client.get("/app/billing", headers={"Accept": "text/html"})
    assert resp.status_code == 200


def test_lead_refresh_blocked_for_expired_trial(client: TestClient, db: Session):
    ctx = _expired_trial_context(client, db)
    lead = ctx["lead"]

    resp = client.post(
        f"/app/leads/{lead.id}/refresh",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers.get("Location") or resp.headers.get("location")
    assert location == "/app/billing"
