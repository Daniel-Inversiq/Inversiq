"""
app/workspace/worker.py

Background worker for workspace processing jobs.

Polls workspace_jobs for NEW entries and dispatches to the processor.
Runs as a daemon thread alongside the existing Job worker.

After all per-document jobs for a workspace are DONE, automatically enqueues
the cross_check job. This sequencing is handled here rather than in the API
to keep the router thin.
"""

from __future__ import annotations

import logging
import time
import threading

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.workspace_job import WorkspaceJob

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # seconds


def _process_job(job: WorkspaceJob, db: Session) -> None:
    from app.workspace.processor import process_workspace_document, run_cross_document_check

    job.status = "IN_PROGRESS"
    db.commit()

    try:
        if job.job_type == "process_document":
            doc_id = (job.payload or {}).get("workspace_doc_id")
            if doc_id:
                process_workspace_document(doc_id, db)
            _maybe_enqueue_cross_check(job.workspace_id, job.tenant_id, db)

        elif job.job_type == "cross_check":
            run_cross_document_check(job.workspace_id, db)

        job.status = "DONE"
        db.commit()

    except Exception as e:
        logger.exception("WorkspaceJob %s failed", job.id)
        job.status = "FAILED"
        job.error_message = str(e)
        db.commit()


def _maybe_enqueue_cross_check(workspace_id: str, tenant_id: str, db: Session) -> None:
    """
    If all process_document jobs for this workspace are DONE (none NEW or IN_PROGRESS),
    enqueue a cross_check job if one isn't already queued or running.
    """
    pending = (
        db.query(WorkspaceJob)
        .filter(
            WorkspaceJob.workspace_id == workspace_id,
            WorkspaceJob.job_type == "process_document",
            WorkspaceJob.status.in_(["NEW", "IN_PROGRESS"]),
        )
        .count()
    )
    if pending > 0:
        return

    already_queued = (
        db.query(WorkspaceJob)
        .filter(
            WorkspaceJob.workspace_id == workspace_id,
            WorkspaceJob.job_type == "cross_check",
            WorkspaceJob.status.in_(["NEW", "IN_PROGRESS"]),
        )
        .count()
    )
    if already_queued > 0:
        return

    cross_check_job = WorkspaceJob(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        job_type="cross_check",
        payload={"workspace_id": workspace_id},
        status="NEW",
    )
    db.add(cross_check_job)
    db.commit()
    logger.info("Enqueued cross_check for workspace %s", workspace_id)


def _worker_loop() -> None:
    while True:
        db: Session = SessionLocal()
        try:
            job = (
                db.query(WorkspaceJob)
                .filter(WorkspaceJob.status == "NEW")
                .order_by(WorkspaceJob.created_at.asc())
                .first()
            )
            if job:
                _process_job(job, db)
        except Exception:
            logger.exception("Unexpected error in workspace worker loop")
        finally:
            db.close()

        time.sleep(POLL_INTERVAL)


def start_workspace_worker() -> None:
    thread = threading.Thread(target=_worker_loop, daemon=True, name="workspace-worker")
    thread.start()
    logger.info("Workspace worker started")
