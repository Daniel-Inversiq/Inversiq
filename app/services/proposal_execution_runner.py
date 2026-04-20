"""
app/services/proposal_execution_runner.py

Execution attempt lifecycle for ProposedChangeExecutionAttempt records.

Provides create / preflight / start / complete / fail / cancel / rollback
operations.  All functions operate within the caller's DB session — they do
NOT commit.  The caller is responsible for committing (or rolling back).

Design:
  - One or more attempts per execution_request_id; keyed by
    (execution_request_id, attempt_number).
  - Attempt number auto-increments from the highest existing attempt.
  - State machine:
      queued  → running     (start, only after preflight passes)
      queued  → cancelled   (cancel)
      running → succeeded   (complete)
      running → failed      (fail)
      running → rolled_back (rollback)
      failed  → rolled_back (rollback)
  - Preflight is evaluated deterministically from execution request snapshots.
  - v1 execution is a controlled stub — no real config mutations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.proposed_change_execution_attempt import ProposedChangeExecutionAttempt
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

# Maps each status to the set of statuses it may transition into
_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    # "failed" is included for preflight failures that short-circuit the queued attempt
    "queued":     frozenset({"running", "cancelled", "failed"}),
    "running":    frozenset({"succeeded", "failed", "rolled_back"}),
    "failed":     frozenset({"rolled_back"}),
    "succeeded":  frozenset(),
    "rolled_back": frozenset(),
    "cancelled":  frozenset(),
}


def _assert_transition(current: str, target: str) -> None:
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(
            f"Invalid attempt transition: '{current}' → '{target}'. "
            f"Allowed from '{current}': {sorted(allowed) or 'none'}."
        )


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

_PREFLIGHT_CHECKS = [
    "request_validated",
    "has_execution_plan",
    "has_monitoring_plan",
    "has_no_blocking_reasons",
    "governance_attestable",
]


def run_preflight_checks(
    request: ProposedChangeExecutionRequest,
) -> dict[str, Any]:
    """
    Evaluate preflight readiness from execution request snapshots.

    Returns a preflight_result_snapshot dict with:
      passed (bool), checks (list), summary (str).

    This is pure computation — no DB writes.
    """
    checks: list[dict[str, Any]] = []

    # 1. Request must be in validated status
    ok = request.status == "validated"
    checks.append({
        "name": "request_validated",
        "passed": ok,
        "detail": (
            "Request status is 'validated'."
            if ok
            else f"Request status is '{request.status}', expected 'validated'."
        ),
    })

    # 2. Execution plan snapshot present
    ok = request.execution_plan_snapshot is not None
    checks.append({
        "name": "has_execution_plan",
        "passed": ok,
        "detail": (
            "Execution plan snapshot is present."
            if ok
            else "Execution plan snapshot is absent."
        ),
    })

    # 3. Monitoring plan snapshot present
    ok = request.monitoring_plan_snapshot is not None
    checks.append({
        "name": "has_monitoring_plan",
        "passed": ok,
        "detail": (
            "Monitoring plan snapshot is present."
            if ok
            else "Monitoring plan snapshot is absent."
        ),
    })

    # 4. No blocking reasons on record
    ok = request.blocking_reasons_snapshot is None
    if not ok:
        try:
            reasons_data = json.loads(request.blocking_reasons_snapshot)
            reasons = reasons_data.get("reasons", [])
            ok = len(reasons) == 0
        except Exception:
            ok = False
    checks.append({
        "name": "has_no_blocking_reasons",
        "passed": ok,
        "detail": (
            "No blocking reasons on record."
            if ok
            else "Blocking reasons are present on the execution request."
        ),
    })

    # 5. Governance snapshot is attestable
    ok = False
    detail = "Governance snapshot is absent."
    if request.governance_snapshot is not None:
        try:
            gov = json.loads(request.governance_snapshot)
            ok = bool(gov.get("attestable"))
            detail = (
                "Governance snapshot is attestable."
                if ok
                else f"Governance snapshot is not attestable: {gov.get('attestation_summary', 'unknown')}."
            )
        except Exception:
            detail = "Governance snapshot could not be parsed."
    checks.append({
        "name": "governance_attestable",
        "passed": ok,
        "detail": detail,
    })

    passed = all(c["passed"] for c in checks)
    failed_names = [c["name"] for c in checks if not c["passed"]]
    summary = (
        "All preflight checks passed."
        if passed
        else f"Preflight failed: {', '.join(failed_names)}."
    )

    return {
        "passed": passed,
        "checks": checks,
        "summary": summary,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Service operations — all do NOT commit
# ---------------------------------------------------------------------------


def create_execution_attempt(
    db: Session,
    *,
    request: ProposedChangeExecutionRequest,
) -> ProposedChangeExecutionAttempt:
    """
    Create a new queued execution attempt for the given request.

    Attempt number is auto-incremented: max(existing attempt_number) + 1,
    or 1 if no prior attempts exist.

    Does NOT commit — caller owns the transaction.
    """
    existing_max = (
        db.query(ProposedChangeExecutionAttempt.attempt_number)
        .filter(
            ProposedChangeExecutionAttempt.execution_request_id == request.id,
        )
        .order_by(ProposedChangeExecutionAttempt.attempt_number.desc())
        .first()
    )
    attempt_number = (existing_max[0] + 1) if existing_max is not None else 1

    attempt = ProposedChangeExecutionAttempt(
        tenant_id=request.tenant_id,
        execution_request_id=request.id,
        change_id=request.change_id,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        status="queued",
        attempt_number=attempt_number,
    )
    db.add(attempt)
    return attempt


def start_execution_attempt(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    preflight_result: dict[str, Any],
) -> ProposedChangeExecutionAttempt:
    """
    Transition an attempt from queued → running.

    Persists the preflight result.  Caller must have already verified that
    preflight passed before calling this function.

    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "running")
    attempt.status = "running"
    attempt.preflight_result_snapshot = json.dumps(preflight_result)
    attempt.started_at = datetime.now(timezone.utc)
    return attempt


def fail_preflight(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    preflight_result: dict[str, Any],
) -> ProposedChangeExecutionAttempt:
    """
    Record a failed preflight and transition queued → failed.

    Used when preflight checks do not pass before start.
    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "failed")
    # We treat a preflight failure as an immediate failed attempt
    attempt.status = "failed"
    attempt.preflight_result_snapshot = json.dumps(preflight_result)
    attempt.failure_reason = preflight_result.get("summary", "Preflight checks failed.")
    attempt.completed_at = datetime.now(timezone.utc)
    return attempt


def complete_execution_attempt(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    execution_result: Optional[dict[str, Any]] = None,
) -> ProposedChangeExecutionAttempt:
    """
    Transition an attempt from running → succeeded.

    Persists execution_result_snapshot.  If no result is supplied, a v1 stub
    result is recorded.  No real config mutations are performed.

    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "succeeded")
    result = execution_result or {
        "outcome": "stub_success",
        "note": (
            "v1 controlled stub — no real config mutations performed. "
            "Outcome recording is a separate step."
        ),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    attempt.status = "succeeded"
    attempt.execution_result_snapshot = json.dumps(result)
    attempt.completed_at = datetime.now(timezone.utc)
    return attempt


def fail_execution_attempt(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    failure_reason: Optional[str] = None,
) -> ProposedChangeExecutionAttempt:
    """
    Transition an attempt from running → failed.

    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "failed")
    attempt.status = "failed"
    attempt.failure_reason = failure_reason or "Execution failed."
    attempt.completed_at = datetime.now(timezone.utc)
    return attempt


def cancel_execution_attempt(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
) -> ProposedChangeExecutionAttempt:
    """
    Transition an attempt from queued → cancelled.

    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "cancelled")
    attempt.status = "cancelled"
    attempt.completed_at = datetime.now(timezone.utc)
    return attempt


def rollback_execution_attempt(
    db: Session,
    *,
    attempt: ProposedChangeExecutionAttempt,
    rollback_snapshot: Optional[dict[str, Any]] = None,
) -> ProposedChangeExecutionAttempt:
    """
    Transition an attempt from running or failed → rolled_back.

    Persists rollback_snapshot.  No real rollback actions are performed in v1;
    this records intent and state only.

    Does NOT commit — caller owns the transaction.
    """
    _assert_transition(attempt.status, "rolled_back")
    snapshot = rollback_snapshot or {
        "note": "v1 controlled stub — rollback state recorded, no real config mutations.",
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
    }
    attempt.status = "rolled_back"
    attempt.rollback_snapshot = json.dumps(snapshot)
    attempt.completed_at = datetime.now(timezone.utc)
    return attempt
