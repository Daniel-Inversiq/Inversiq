from __future__ import annotations

import json
import uuid

import pytest

from app.auth.jwt import create_access_token
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.user import User


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _seed_user_and_lead(db) -> tuple[User, Lead]:
    tenant_id = _uid("tenant")
    user_id = _uid("user")
    lead_id = _uid("lead")

    tenant = Tenant(
        id=tenant_id,
        name="Quote Edit Tenant",
        subscription_status="active",
        plan_code="pro",
    )
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.com",
        password_hash="not-used",
        is_active=True,
    )
    lead = Lead(
        id=lead_id,
        tenant_id=tenant_id,
        name="Quote Edit Lead",
        email=f"{lead_id}@example.com",
        status="SUCCEEDED",
        estimate_json=json.dumps(
            {
                "line_items": [],
                "totals": {"pre_tax": 100.0, "tax_amount": 21.0, "grand_total": 121.0},
                "meta": {"title": "Offerte"},
            }
        ),
        estimate_overrides_json=json.dumps({}),
    )

    db.add(tenant)
    db.add(user)
    db.add(lead)
    db.commit()
    db.refresh(user)
    db.refresh(lead)
    return user, lead


def _auth_headers_for_user(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


def _post_quote_edit(client, lead_id: str, headers: dict[str, str], payload: dict[str, str]):
    return client.post(
        f"/app/quotes/{lead_id}/edit",
        data=payload,
        headers=headers,
        follow_redirects=False,
    )


@pytest.mark.parametrize(
    ("discount_percent", "manual_total", "expected_discount", "expected_manual"),
    [
        ("", "", None, None),  # both empty
        ("5", "", 5.0, None),  # only discount
        ("", "2450", None, 2450.0),  # only manual total
        ("10", "2000", 10.0, 2000.0),  # both filled
        ("5.5", "2450.75", 5.5, 2450.75),  # decimal values
        ("0", "0", 0.0, 0.0),  # zero values
    ],
)
def test_quote_edit_optional_numeric_fields_are_parsed_safely(
    client, db, monkeypatch, discount_percent, manual_total, expected_discount, expected_manual
):
    user, lead = _seed_user_and_lead(db)
    headers = _auth_headers_for_user(user)

    # Keep the test focused on form parsing and persistence, not rendering side-effects.
    monkeypatch.setattr(
        "app.verticals.construction.router_app.render_quote_html_for_lead",
        lambda _lead, _estimate_dict, _overrides: (None, False),
    )

    payload = {
        "discount_percent": discount_percent,
        "manual_total": manual_total,
    }
    response = _post_quote_edit(client, lead.id, headers, payload)

    assert response.status_code == 303
    assert response.headers.get("location") == f"/offertes/{lead.id}/bewerken"

    db.expire_all()
    refreshed = db.query(Lead).filter(Lead.id == lead.id).first()
    assert refreshed is not None
    overrides = json.loads(refreshed.estimate_overrides_json or "{}")
    assert overrides.get("discount_percent") == expected_discount
    assert overrides.get("manual_total") == expected_manual


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("discount_percent", "abc"),
        ("manual_total", "not-a-number"),
    ],
)
def test_quote_edit_invalid_numeric_text_returns_field_specific_422(
    client, db, monkeypatch, field_name, bad_value
):
    user, lead = _seed_user_and_lead(db)
    headers = _auth_headers_for_user(user)

    monkeypatch.setattr(
        "app.verticals.construction.router_app.render_quote_html_for_lead",
        lambda _lead, _estimate_dict, _overrides: (None, False),
    )

    payload = {
        "discount_percent": "",
        "manual_total": "",
        field_name: bad_value,
    }
    response = _post_quote_edit(client, lead.id, headers, payload)

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert field_name in str(body["detail"])


def test_quote_edit_recomputes_totals_from_line_items_for_persistence(client, db, monkeypatch):
    user, lead = _seed_user_and_lead(db)
    headers = _auth_headers_for_user(user)

    monkeypatch.setattr(
        "app.verticals.construction.router_app.render_quote_html_for_lead",
        lambda _lead, _estimate_dict, _overrides: (None, False),
    )

    payload = {
        "line_items_json": json.dumps(
            [
                {
                    "code": "item_1",
                    "label": "Werkzaamheden",
                    "description": "",
                    "quantity": 15,
                    "unit": "job",
                    "unit_price": 25,
                    "category": "labor",
                }
            ]
        ),
        "discount_percent": "",
        "manual_total": "",
        "subtotal_excl": "375",
        "vat_rate_percent": "21",
    }

    response = _post_quote_edit(client, lead.id, headers, payload)
    assert response.status_code == 303

    db.expire_all()
    refreshed = db.query(Lead).filter(Lead.id == lead.id).first()
    assert refreshed is not None

    estimate = json.loads(refreshed.estimate_json or "{}")
    totals = estimate.get("totals") or {}
    assert totals.get("pre_tax") == 375.0
    assert totals.get("tax_amount") == 78.75
    assert totals.get("grand_total") == 453.75


def test_quote_edit_priced_lines_clear_review_flags_for_public_render(client, db, monkeypatch):
    user, lead = _seed_user_and_lead(db)
    headers = _auth_headers_for_user(user)

    # Simulate a lead that still carries review flags from earlier AI output.
    estimate = json.loads(lead.estimate_json or "{}")
    estimate["needs_review"] = True
    estimate["review_reasons"] = ["surface_damage_detected"]
    meta = estimate.get("meta") or {}
    meta["needs_review"] = True
    meta["needs_review_reasons"] = ["surface_damage_detected"]
    meta["review_reasons"] = ["surface_damage_detected"]
    estimate["meta"] = meta
    lead.estimate_json = json.dumps(estimate)
    db.add(lead)
    db.commit()

    monkeypatch.setattr(
        "app.verticals.construction.router_app.render_quote_html_for_lead",
        lambda _lead, _estimate_dict, _overrides: (None, False),
    )

    payload = {
        "line_items_json": json.dumps(
            [
                {
                    "code": "item_1",
                    "label": "Werkzaamheden",
                    "description": "",
                    "quantity": 15,
                    "unit": "job",
                    "unit_price": 25,
                    "category": "labor",
                }
            ]
        ),
        "discount_percent": "",
        "manual_total": "",
        "subtotal_excl": "375",
        "vat_rate_percent": "21",
    }

    response = _post_quote_edit(client, lead.id, headers, payload)
    assert response.status_code == 303

    db.expire_all()
    refreshed = db.query(Lead).filter(Lead.id == lead.id).first()
    assert refreshed is not None

    estimate_after = json.loads(refreshed.estimate_json or "{}")
    meta_after = estimate_after.get("meta") or {}
    assert estimate_after.get("needs_review") is False
    assert estimate_after.get("review_reasons") == []
    assert meta_after.get("needs_review") is False
    assert meta_after.get("needs_review_reasons") == []
    assert meta_after.get("review_reasons") == []
