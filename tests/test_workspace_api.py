"""
Integration tests for the Workspace API.

Uses an in-memory SQLite database — no external services required.
Does NOT call the LLM (processor is not invoked; only the API layer is tested).
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SECRET_KEY", "test-secret")

import app.models  # noqa — ensure all models are registered before create_all
from app.db import Base, engine, get_db
from app.main import app as fastapi_app

# Ensure workspace tables exist in the test DB.
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db_session():
    """Each test gets a rolled-back session — no cross-test contamination."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_db
    headers = {"Authorization": "Bearer demo-token"}
    with TestClient(fastapi_app, raise_server_exceptions=False, headers=headers) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def test_create_workspace(client):
    resp = client.post("/api/workspaces", json={"name": "Basingstoke", "vertical_id": "cre", "tenant_id": "test-tenant"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Basingstoke"
    assert data["status"] == "pending"
    assert data["vertical_id"] == "cre"
    assert len(data["id"]) == 32


def test_list_workspaces(client):
    client.post("/api/workspaces", json={"name": "W1", "tenant_id": "t1"})
    client.post("/api/workspaces", json={"name": "W2", "tenant_id": "t1"})
    client.post("/api/workspaces", json={"name": "W3", "tenant_id": "other"})

    resp = client.get("/api/workspaces?tenant_id=t1")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(w["tenant_id"] == "t1" for w in items)


def test_get_workspace_not_found(client):
    resp = client.get("/api/workspaces/doesnotexist")
    assert resp.status_code == 404


def test_register_document(client):
    ws = client.post("/api/workspaces", json={"name": "Test", "tenant_id": "t1"}).json()
    ws_id = ws["id"]

    resp = client.post(f"/api/workspaces/{ws_id}/documents", json={"filename": "RentRoll.xlsx"})
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["filename"] == "RentRoll.xlsx"
    assert doc["status"] == "uploaded"
    assert doc["doc_type"] is None


def test_workspace_detail_includes_documents_and_flags(client):
    ws = client.post("/api/workspaces", json={"name": "Test", "tenant_id": "t1"}).json()
    ws_id = ws["id"]
    client.post(f"/api/workspaces/{ws_id}/documents", json={"filename": "IM.pdf"})
    client.post(f"/api/workspaces/{ws_id}/documents", json={"filename": "RentRoll.xlsx"})

    resp = client.get(f"/api/workspaces/{ws_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["documents"]) == 2
    assert data["flags"] == []
    assert data["open_flag_count"] == 0


def test_process_requires_documents(client):
    ws = client.post("/api/workspaces", json={"name": "Empty", "tenant_id": "t1"}).json()
    resp = client.post(f"/api/workspaces/{ws['id']}/process")
    assert resp.status_code == 400


def test_process_enqueues_jobs(client):
    ws = client.post("/api/workspaces", json={"name": "Test", "tenant_id": "t1"}).json()
    ws_id = ws["id"]
    client.post(f"/api/workspaces/{ws_id}/documents", json={"filename": "IM.pdf"})
    client.post(f"/api/workspaces/{ws_id}/documents", json={"filename": "RentRoll.xlsx"})

    resp = client.post(f"/api/workspaces/{ws_id}/process")
    assert resp.status_code == 202
    data = resp.json()
    assert len(data["enqueued_document_ids"]) == 2

    # Workspace status transitions to processing
    status_resp = client.get(f"/api/workspaces/{ws_id}/status")
    assert status_resp.json()["status"] == "processing"


def test_resolve_flag(client, db_session):
    from app.models.workspace import WorkspaceFlag

    ws_resp = client.post("/api/workspaces", json={"name": "Test", "tenant_id": "t1"}).json()
    ws_id = ws_resp["id"]

    # Insert a flag directly into the shared session
    flag = WorkspaceFlag(
        workspace_id=ws_id,
        flag_type="erv_deviation",
        severity="high",
        title="ERV Conflict",
        detail="ERVs differ by 12%",
        status="open",
    )
    db_session.add(flag)
    db_session.flush()
    flag_id = flag.id

    resp = client.patch(
        f"/api/workspaces/{ws_id}/flags/{flag_id}",
        json={"action": "resolve", "resolution_note": "Accepted valuation figure", "resolved_by": "analyst"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_by"] == "analyst"
    assert data["resolution_note"] == "Accepted valuation figure"

    # Workspace should now be ready (all flags resolved)
    ws_detail = client.get(f"/api/workspaces/{ws_id}").json()
    assert ws_detail["status"] == "ready"


def test_cross_checks_logic():
    from app.workspace.cross_checks import run_all_checks

    docs = [
        {"id": 1, "filename": "RentRoll.xlsx", "doc_type": "rent_roll",
         "extracted_data": {"fields": {"average_erv_psm": 85, "total_gla_sqm": 117000}, "confidence": 0.9}},
        {"id": 2, "filename": "Valuation.pdf", "doc_type": "valuation_report",
         "extracted_data": {"fields": {"erv_psm_warehouse": 96, "market_value": 155000000}, "confidence": 0.88}},
        {"id": 3, "filename": "TDD.pdf", "doc_type": "tdd_report",
         "extracted_data": {"fields": {"category_1_capex": 340000}, "confidence": 0.85}},
        {"id": 4, "filename": "IM.pdf", "doc_type": "information_memorandum",
         "extracted_data": {"fields": {"total_gla_sqm": 117000, "asking_price": 155000000}, "confidence": 0.9}},
    ]

    flags = run_all_checks(docs)
    flag_types = {f["flag_type"] for f in flags}

    assert "erv_deviation" in flag_types       # 96 vs 85 = 13% delta
    assert "capex_undisclosed" in flag_types   # TDD capex not in IM
    assert "gla_inconsistency" not in flag_types  # same GLA, no flag
    assert all(f["severity"] in ("high", "medium", "low") for f in flags)
