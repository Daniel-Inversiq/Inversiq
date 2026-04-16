from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.anomaly.engine import run_all
from app.anomaly.types import AnomalyType
from app.auth.deps import require_user_html
from app.db import get_db
from app.i18n.service import setup_jinja_i18n
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.routers.pipeline_runs import build_pipeline_run_debug_payload

router = APIRouter(prefix="/ops", tags=["ops"])
templates = Jinja2Templates(directory="app/templates")
setup_jinja_i18n(templates)


@router.get("/runs", response_class=HTMLResponse, name="ops_runs")
def ops_runs(
    request: Request,
    status: Optional[str] = Query(default=None),
    tenant_id: Optional[str] = Query(default=None),
    lead_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    q = db.query(PipelineRun)
    if status:
        q = q.filter(PipelineRun.status == status.upper())
    if tenant_id:
        q = q.filter(PipelineRun.tenant_id == tenant_id.strip())
    if lead_id:
        q = q.filter(PipelineRun.lead_id == lead_id.strip())

    runs = q.order_by(PipelineRun.id.desc()).limit(limit).all()
    return templates.TemplateResponse(
        "ops_runs.html",
        {
            "request": request,
            "current_user": current_user,
            "runs": runs,
            "filters": {
                "status": status or "",
                "tenant_id": tenant_id or "",
                "lead_id": lead_id or "",
                "limit": limit,
            },
        },
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse, name="ops_run_detail")
def ops_run_detail(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    payload = build_pipeline_run_debug_payload(db, run_id)
    return templates.TemplateResponse(
        "ops_run_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "payload": payload,
            "run_id": run_id,
        },
    )


@router.get("/anomalies", response_class=HTMLResponse, name="ops_anomalies")
def ops_anomalies(
    request: Request,
    tenant_id: Optional[str] = Query(default=None),
    anomaly_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_html),
):
    resolved_type: Optional[AnomalyType] = None
    anomaly_type_clean = (anomaly_type or "").strip().upper()
    if anomaly_type_clean:
        try:
            resolved_type = AnomalyType(anomaly_type_clean)
        except ValueError:
            resolved_type = None

    anomalies = run_all(
        db,
        tenant_id=(tenant_id or "").strip() or None,
        anomaly_type=resolved_type,
    )
    items = [a.to_dict() for a in anomalies]
    total = len(items)
    items = items[:limit]

    return templates.TemplateResponse(
        "ops_anomalies.html",
        {
            "request": request,
            "current_user": current_user,
            "anomalies": items,
            "total": total,
            "shown_count": len(items),
            "anomaly_types": [t.value for t in AnomalyType],
            "filters": {
                "tenant_id": tenant_id or "",
                "anomaly_type": resolved_type.value if resolved_type else "",
                "limit": limit,
            },
        },
    )
