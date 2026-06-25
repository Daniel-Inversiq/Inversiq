"""
app/routers/workspaces.py

REST API for the Workspace intelligence layer.

POST   /api/workspaces                      — create workspace
GET    /api/workspaces                      — list workspaces (tenant-scoped)
GET    /api/workspaces/{id}                 — workspace detail with documents + flags
POST   /api/workspaces/{id}/documents       — register a document (after S3 upload)
POST   /api/workspaces/{id}/process         — trigger processing pipeline
GET    /api/workspaces/{id}/status          — lightweight polling status endpoint
PATCH  /api/workspaces/{id}/flags/{flag_id} — resolve or escalate a flag
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.workspace import Workspace, WorkspaceDocument, WorkspaceFlag
from app.models.workspace_job import WorkspaceJob

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateWorkspaceRequest(BaseModel):
    name: str
    vertical_id: str = "cre"
    tenant_id: str = "demo"


class RegisterDocumentRequest(BaseModel):
    filename: str
    upload_record_id: Optional[int] = None


class ResolveFlagRequest(BaseModel):
    action: str  # "resolve" | "escalate"
    resolution_note: Optional[str] = None
    resolution_value: Optional[str] = None
    resolved_by: Optional[str] = "operator"


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _serialise_flag(f: WorkspaceFlag) -> dict[str, Any]:
    return {
        "id": f.id,
        "flag_type": f.flag_type,
        "severity": f.severity,
        "title": f.title,
        "detail": f.detail,
        "source_document_ids": f.source_document_ids or [],
        "conflict_data": f.conflict_data or {},
        "status": f.status,
        "resolved_by": f.resolved_by,
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "resolution_note": f.resolution_note,
        "resolution_value": f.resolution_value,
        "created_at": f.created_at.isoformat(),
    }


def _serialise_document(d: WorkspaceDocument) -> dict[str, Any]:
    return {
        "id": d.id,
        "filename": d.filename,
        "doc_type": d.doc_type,
        "classification_confidence": d.classification_confidence,
        "status": d.status,
        "error_message": d.error_message,
        "extracted_data": d.extracted_data,
        "upload_record_id": d.upload_record_id,
        "pipeline_run_id": d.pipeline_run_id,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


def _serialise_workspace(w: Workspace, include_detail: bool = False) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": w.id,
        "tenant_id": w.tenant_id,
        "name": w.name,
        "vertical_id": w.vertical_id,
        "status": w.status,
        "overall_confidence": w.overall_confidence,
        "pipeline_run_id": w.pipeline_run_id,
        "created_at": w.created_at.isoformat(),
        "updated_at": w.updated_at.isoformat(),
    }
    if include_detail:
        base["documents"] = [_serialise_document(d) for d in w.documents]
        base["flags"] = [_serialise_flag(f) for f in w.flags]
        base["extracted_summary"] = w.extracted_summary or {}
        open_flags = [f for f in w.flags if f.status == "open"]
        base["open_flag_count"] = len(open_flags)
        base["high_severity_count"] = sum(1 for f in open_flags if f.severity == "high")
    return base


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_workspace(body: CreateWorkspaceRequest, db: Session = Depends(get_db)) -> dict:
    workspace = Workspace(
        id=uuid.uuid4().hex,
        tenant_id=body.tenant_id,
        name=body.name,
        vertical_id=body.vertical_id,
        status="pending",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return _serialise_workspace(workspace)


@router.get("")
def list_workspaces(
    tenant_id: str = Query("demo"),
    db: Session = Depends(get_db),
) -> list[dict]:
    workspaces = (
        db.query(Workspace)
        .filter(Workspace.tenant_id == tenant_id)
        .order_by(Workspace.created_at.desc())
        .limit(50)
        .all()
    )
    return [_serialise_workspace(w) for w in workspaces]


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, db: Session = Depends(get_db)) -> dict:
    w = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _serialise_workspace(w, include_detail=True)


@router.post("/{workspace_id}/documents", status_code=201)
def register_document(
    workspace_id: str,
    body: RegisterDocumentRequest,
    db: Session = Depends(get_db),
) -> dict:
    w = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workspace not found")

    doc = WorkspaceDocument(
        workspace_id=workspace_id,
        filename=body.filename,
        upload_record_id=body.upload_record_id,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _serialise_document(doc)


@router.post("/{workspace_id}/process", status_code=202)
def trigger_processing(workspace_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Enqueue process_document jobs for all uploaded documents.
    The worker auto-enqueues the cross_check job once all documents are done.
    """
    w = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workspace not found")

    docs = (
        db.query(WorkspaceDocument)
        .filter(
            WorkspaceDocument.workspace_id == workspace_id,
            WorkspaceDocument.status == "uploaded",
        )
        .all()
    )

    if not docs:
        raise HTTPException(
            status_code=400,
            detail="No uploaded documents found. Register documents before processing.",
        )

    enqueued = []
    for doc in docs:
        job = WorkspaceJob(
            tenant_id=w.tenant_id,
            workspace_id=workspace_id,
            job_type="process_document",
            payload={"workspace_doc_id": doc.id},
            status="NEW",
        )
        db.add(job)
        enqueued.append(doc.id)

    w.status = "processing"
    db.commit()

    return {
        "workspace_id": workspace_id,
        "enqueued_document_ids": enqueued,
        "message": f"Processing started for {len(enqueued)} document(s).",
    }


@router.get("/{workspace_id}/status")
def get_workspace_status(workspace_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Lightweight polling endpoint. Returns workspace status + per-document status.
    Frontend polls this every 2s to drive the live processing feed.
    """
    w = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Workspace not found")

    docs = (
        db.query(WorkspaceDocument)
        .filter(WorkspaceDocument.workspace_id == workspace_id)
        .order_by(WorkspaceDocument.created_at)
        .all()
    )

    flags = (
        db.query(WorkspaceFlag)
        .filter(WorkspaceFlag.workspace_id == workspace_id)
        .all()
    )

    open_flags = [f for f in flags if f.status == "open"]

    return {
        "workspace_id": workspace_id,
        "status": w.status,
        "overall_confidence": w.overall_confidence,
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "doc_type": d.doc_type,
                "status": d.status,
                "classification_confidence": d.classification_confidence,
            }
            for d in docs
        ],
        "open_flag_count": len(open_flags),
        "high_severity_count": sum(1 for f in open_flags if f.severity == "high"),
        "flags": [_serialise_flag(f) for f in flags],
    }


@router.patch("/{workspace_id}/flags/{flag_id}")
def resolve_flag(
    workspace_id: str,
    flag_id: int,
    body: ResolveFlagRequest,
    db: Session = Depends(get_db),
) -> dict:
    flag = (
        db.query(WorkspaceFlag)
        .filter(
            WorkspaceFlag.id == flag_id,
            WorkspaceFlag.workspace_id == workspace_id,
        )
        .first()
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    if body.action not in ("resolve", "escalate"):
        raise HTTPException(status_code=400, detail="action must be 'resolve' or 'escalate'")

    flag.status = "resolved" if body.action == "resolve" else "escalated"
    flag.resolved_by = body.resolved_by or "operator"
    flag.resolved_at = datetime.now(timezone.utc)
    flag.resolution_note = body.resolution_note
    flag.resolution_value = body.resolution_value
    db.commit()

    # If all flags are resolved/escalated, mark workspace ready
    remaining_open = (
        db.query(WorkspaceFlag)
        .filter(
            WorkspaceFlag.workspace_id == workspace_id,
            WorkspaceFlag.status == "open",
        )
        .count()
    )
    if remaining_open == 0:
        w = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if w:
            w.status = "ready"
            db.commit()

    return _serialise_flag(flag)
