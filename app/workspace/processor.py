"""
app/workspace/processor.py

Workspace document processing pipeline.

Entry points:
  process_workspace_document(workspace_doc_id, db)  — classify + extract one document
  run_cross_document_check(workspace_id, db)         — cross-document validation → flags

Called by the Job runner. Each function is synchronous and manages its own
DB transaction scope. PipelineRun / PipelineStepRun rows are written so the
existing observability layer (review inbox, anomaly detection) picks them up.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun, PipelineStepRun
from app.models.workspace import Workspace, WorkspaceDocument, WorkspaceFlag
from app.workspace.cross_checks import run_all_checks

logger = logging.getLogger(__name__)

_ENGINE_VERSION = "workspace-pipeline-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_file_text(doc: WorkspaceDocument, db: Session) -> str:
    """
    Read file content for extraction. For the demo we use local storage;
    production will read from S3 via the existing s3_storage service.
    """
    from app.models.upload_record import UploadRecord
    from app.core.settings import settings
    import os

    if not doc.upload_record_id:
        return f"[filename: {doc.filename}]"

    upload = db.query(UploadRecord).filter(UploadRecord.id == doc.upload_record_id).first()
    if not upload or not upload.object_key:
        return f"[filename: {doc.filename}]"

    # Local storage path
    local_path = os.path.join(settings.LOCAL_STORAGE_ROOT, upload.object_key)
    if not os.path.exists(local_path):
        # Try alternate path
        local_path = os.path.join(settings.LOCAL_STORAGE_PATH, upload.object_key)

    if os.path.exists(local_path):
        try:
            if upload.mime == "application/pdf":
                return _extract_pdf_text(local_path)
            elif upload.mime in ("application/vnd.ms-excel",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
                return _extract_excel_text(local_path)
            else:
                with open(local_path, "r", errors="replace") as f:
                    return f.read(10000)
        except Exception as e:
            logger.warning("Failed to read file %s: %s", local_path, e)

    return f"[filename: {doc.filename}] [content unavailable]"


def _extract_pdf_text(path: str) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages[:10]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)[:10000]
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            parts = [p.extract_text() or "" for p in pdf.pages[:10]]
            return "\n".join(parts)[:10000]
    except ImportError:
        pass
    return f"[PDF file — text extraction unavailable. Install pypdf or pdfplumber.]"


def _extract_excel_text(path: str) -> str:
    try:
        import pandas as pd
        xl = pd.ExcelFile(path, engine="openpyxl")
        parts = []
        for sheet in xl.sheet_names[:5]:
            df = xl.parse(sheet, header=None)
            flat = df.stack().dropna().reset_index()
            flat.columns = ["r", "c", "v"]
            vals = flat[flat["v"].astype(str).str.len() > 1]["v"].unique()
            parts.append(f"[Sheet: {sheet}]\n" + " | ".join(str(v)[:50] for v in vals[:100]))
        return "\n\n".join(parts)[:10000]
    except Exception as e:
        return f"[Excel file — extraction error: {e}]"


def _create_pipeline_run(
    workspace: Workspace,
    pipeline_name: str,
    db: Session,
) -> PipelineRun:
    run = PipelineRun(
        tenant_id=workspace.tenant_id,
        lead_id=workspace.id,           # workspace.id reuses the lead_id slot generically
        vertical_id=workspace.vertical_id,
        trace_id=uuid.uuid4().hex,
        pipeline_name=pipeline_name,
        engine_version=_ENGINE_VERSION,
        status="RUNNING",
        started_at=_now(),
    )
    db.add(run)
    db.flush()
    return run


def _add_step(
    run: PipelineRun,
    step_name: str,
    order: int,
    status: str,
    output: dict | None = None,
    confidence_score: float | None = None,
    confidence_label: str | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    db: Session | None = None,
) -> PipelineStepRun:
    step = PipelineStepRun(
        pipeline_run_id=run.id,
        step_name=step_name,
        step_order=order,
        status=status,
        output_snapshot=output,
        confidence_score=confidence_score,
        confidence_label=confidence_label or (
            "high" if (confidence_score or 0) >= 0.75
            else "medium" if (confidence_score or 0) >= 0.50
            else "low"
        ) if confidence_score is not None else None,
        error_message=error_message,
        duration_ms=duration_ms,
        started_at=_now(),
        completed_at=_now(),
    )
    return step


# ---------------------------------------------------------------------------
# Per-document processor
# ---------------------------------------------------------------------------

def process_workspace_document(workspace_doc_id: int, db: Session) -> None:
    """
    Classify and extract a single WorkspaceDocument.

    Steps:
      1. classify   — determine doc_type + confidence
      2. extract    — pull structured fields from the document
      3. validate   — field-level rule checks (required fields, date formats)
    """
    doc = db.query(WorkspaceDocument).filter(WorkspaceDocument.id == workspace_doc_id).first()
    if not doc:
        logger.error("WorkspaceDocument %s not found", workspace_doc_id)
        return

    workspace = db.query(Workspace).filter(Workspace.id == doc.workspace_id).first()
    if not workspace:
        logger.error("Workspace %s not found", doc.workspace_id)
        return

    doc.status = "classifying"
    db.commit()

    run = _create_pipeline_run(workspace, f"document.classify_extract.{doc.filename}", db)
    doc.pipeline_run_id = run.id
    db.commit()

    steps = []
    overall_confidence = 1.0

    # ── Step 1: Classify ──────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        from app.workspace.llm import classify_document
        text_sample = _read_file_text(doc, db)
        result = classify_document(doc.filename, text_sample)
        doc_type = result["doc_type"]
        conf = float(result.get("confidence", 0.8))
        duration_ms = int((time.monotonic() - t0) * 1000)

        doc.doc_type = doc_type
        doc.classification_confidence = str(round(conf, 3))
        doc.status = "extracting"
        db.commit()

        steps.append(_add_step(
            run, "classify", 1, "COMPLETED",
            output=result, confidence_score=conf,
            duration_ms=duration_ms,
        ))
        overall_confidence = min(overall_confidence, conf)

    except Exception as e:
        logger.exception("classify step failed for doc %s", workspace_doc_id)
        doc.status = "failed"
        doc.error_message = f"Classification failed: {e}"
        run.status = "FAILED"
        run.failure_step = "classify"
        run.completed_at = _now()
        db.add_all(steps)
        db.commit()
        return

    # ── Step 2: Extract ───────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        from app.workspace.llm import extract_document
        text_full = _read_file_text(doc, db)
        extraction = extract_document(doc_type, text_full)
        conf_ext = float(extraction.get("confidence", 0.7))
        duration_ms = int((time.monotonic() - t0) * 1000)

        doc.extracted_data = extraction
        doc.status = "extracted"
        db.commit()

        steps.append(_add_step(
            run, "extract", 2, "COMPLETED",
            output={"doc_type": doc_type, "field_count": len(extraction.get("fields", {}))},
            confidence_score=conf_ext,
            duration_ms=duration_ms,
        ))
        overall_confidence = min(overall_confidence, conf_ext)

    except Exception as e:
        logger.exception("extract step failed for doc %s", workspace_doc_id)
        doc.status = "failed"
        doc.error_message = f"Extraction failed: {e}"
        run.status = "FAILED"
        run.failure_step = "extract"
        run.completed_at = _now()
        db.add_all(steps)
        db.commit()
        return

    # ── Step 3: Validate ──────────────────────────────────────────────────
    t0 = time.monotonic()
    missing = extraction.get("missing_required", [])
    val_conf = 1.0 - (0.15 * len(missing))
    val_conf = max(val_conf, 0.0)

    steps.append(_add_step(
        run, "validate", 3, "COMPLETED",
        output={"missing_required": missing, "issue_count": len(missing)},
        confidence_score=val_conf,
        duration_ms=int((time.monotonic() - t0) * 1000),
    ))
    overall_confidence = min(overall_confidence, val_conf)

    # ── Finish ────────────────────────────────────────────────────────────
    doc.status = "validated"
    run.status = "COMPLETED"
    run.overall_confidence_score = overall_confidence
    run.overall_confidence_label = (
        "high" if overall_confidence >= 0.75
        else "medium" if overall_confidence >= 0.50
        else "low"
    )
    run.completed_at = _now()
    db.add_all(steps)
    db.commit()

    logger.info(
        "Document %s processed: type=%s confidence=%.2f",
        workspace_doc_id, doc_type, overall_confidence,
    )


# ---------------------------------------------------------------------------
# Cross-document checker
# ---------------------------------------------------------------------------

def run_cross_document_check(workspace_id: str, db: Session) -> None:
    """
    Run cross-document consistency checks for all documents in the workspace.
    Emits WorkspaceFlag rows. Updates workspace status to needs_review or ready.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        logger.error("Workspace %s not found", workspace_id)
        return

    workspace.status = "processing"
    db.commit()

    docs = (
        db.query(WorkspaceDocument)
        .filter(
            WorkspaceDocument.workspace_id == workspace_id,
            WorkspaceDocument.status.in_(["validated", "extracted"]),
        )
        .all()
    )

    # Build a serializable list for the check functions (no SQLAlchemy objects)
    doc_dicts = [
        {
            "id": d.id,
            "filename": d.filename,
            "doc_type": d.doc_type,
            "extracted_data": d.extracted_data,
        }
        for d in docs
    ]

    run = _create_pipeline_run(workspace, "workspace.cross_document_check", db)
    workspace.pipeline_run_id = run.id
    db.commit()

    t0 = time.monotonic()
    try:
        flag_specs = run_all_checks(doc_dicts)
    except Exception as e:
        logger.exception("cross_document_check failed for workspace %s", workspace_id)
        run.status = "FAILED"
        run.failure_step = "cross_check"
        run.completed_at = _now()
        workspace.status = "failed"
        db.commit()
        return

    duration_ms = int((time.monotonic() - t0) * 1000)

    # Delete existing open flags before re-emitting (idempotent re-runs)
    db.query(WorkspaceFlag).filter(
        WorkspaceFlag.workspace_id == workspace_id,
        WorkspaceFlag.status == "open",
    ).delete(synchronize_session=False)

    for spec in flag_specs:
        flag = WorkspaceFlag(
            workspace_id=workspace_id,
            flag_type=spec["flag_type"],
            severity=spec["severity"],
            title=spec["title"],
            detail=spec["detail"],
            source_document_ids=spec.get("source_document_ids", []),
            conflict_data=spec.get("conflict_data"),
            status="open",
        )
        db.add(flag)

    open_flag_count = len(flag_specs)

    step = _add_step(
        run, "cross_check", 1, "COMPLETED",
        output={"flags_emitted": open_flag_count, "doc_count": len(docs)},
        confidence_score=1.0,
        duration_ms=duration_ms,
    )
    db.add(step)

    run.status = "COMPLETED"
    run.overall_confidence_score = 1.0
    run.completed_at = _now()

    workspace.status = "needs_review" if open_flag_count > 0 else "ready"

    # Aggregate extracted summaries across documents
    workspace.extracted_summary = _build_summary(doc_dicts)

    db.commit()

    logger.info(
        "Workspace %s cross-check complete: %d flags, status=%s",
        workspace_id, open_flag_count, workspace.status,
    )


def _build_summary(doc_dicts: list[dict]) -> dict[str, Any]:
    """Merge key extracted fields across documents into a flat workspace summary."""
    summary: dict[str, Any] = {}

    for d in doc_dicts:
        fields = (d.get("extracted_data") or {}).get("fields", {})
        doc_type = d.get("doc_type", "")

        if doc_type == "information_memorandum":
            for key in ("asset_name", "location", "asking_price", "currency",
                        "total_gla_sqm", "passing_rent_annual", "gross_initial_yield_pct"):
                if fields.get(key) and not summary.get(key):
                    summary[key] = fields[key]

        elif doc_type == "rent_roll":
            for key in ("total_gla_sqm", "total_passing_rent_annual", "average_erv_psm",
                        "number_of_tenants", "vacancy_sqm"):
                if fields.get(key):
                    summary[f"rent_roll_{key}"] = fields[key]
            if fields.get("tenants"):
                summary["tenants"] = fields["tenants"]

        elif doc_type == "valuation_report":
            for key in ("market_value", "net_initial_yield_pct", "erv_psm_warehouse",
                        "erv_psm_office", "void_assumption_months"):
                if fields.get(key):
                    summary[f"valuation_{key}"] = fields[key]

        elif doc_type == "tdd_report":
            for key in ("category_1_capex", "category_2_capex", "total_capex", "epc_rating"):
                if fields.get(key):
                    summary[f"tdd_{key}"] = fields[key]

        elif doc_type == "loan_termsheet":
            for key in ("loan_amount", "ltv_pct", "margin_bps", "term_years"):
                if fields.get(key):
                    summary[f"loan_{key}"] = fields[key]

    return summary
