"""
tests/test_proposed_change_execution_outcome.py

Unit tests for the proposal_execution_outcome service layer.

Tests:
  - improved classification
  - neutral classification
  - degraded classification
  - unstable classification
  - rollback_triggered true when threshold crossed
  - graceful handling of missing metrics
  - graceful handling of scalar-only metrics (no baseline)
  - graceful handling of zero baseline
  - re-recording overwrites existing outcome
  - record_execution_outcome persists correctly
  - tenant isolation
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.models.proposed_change_execution_outcome import ProposedChangeExecutionOutcome
from app.models.proposed_change_execution_request import ProposedChangeExecutionRequest
from app.services.proposal_execution_outcome import (
    evaluate_execution_outcome,
    record_execution_outcome,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_exec_request(
    id_: int = 1,
    tenant_id: str = "tenant_a",
    change_id: str = "pipeline:pipe1:threshold:none",
    change_type: str = "threshold_adjustment",
    monitoring_plan: dict | None = None,
) -> MagicMock:
    req = MagicMock(spec=ProposedChangeExecutionRequest)
    req.id = id_
    req.tenant_id = tenant_id
    req.change_id = change_id
    req.scope_type = "pipeline"
    req.scope_id = "pipe1"
    req.change_type = change_type
    if monitoring_plan is None:
        monitoring_plan = {
            "change_type": change_type,
            "metrics_to_watch": ["failed_rate", "review_rate", "throughput"],
            "rollback_triggers": ["failed_rate worsens by more than 10%"],
            "observation_window_hours": 24,
        }
    req.monitoring_plan_snapshot = json.dumps(monitoring_plan)
    return req


def _metric(value: float, baseline: float, direction: str = "lower_is_better") -> dict:
    return {"value": value, "baseline": baseline, "direction": direction}


# ---------------------------------------------------------------------------
# evaluate_execution_outcome — classification
# ---------------------------------------------------------------------------


def test_evaluate_improved():
    plan = {
        "metrics_to_watch": ["failed_rate", "review_rate"],
        "rollback_triggers": [],
    }
    observed = {
        "failed_rate": _metric(0.03, 0.06),  # improved: dropped 50%
        "review_rate": _metric(0.08, 0.12),  # improved: dropped ~33%
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "improved"
    assert result["rollback_triggered"] is False
    assert result["rollback_reason"] is None
    assert result["deviation_snapshot"]["failed_rate"]["verdict"] == "improved"
    assert result["deviation_snapshot"]["review_rate"]["verdict"] == "improved"


def test_evaluate_neutral_small_change():
    plan = {"metrics_to_watch": ["failed_rate"], "rollback_triggers": []}
    observed = {
        "failed_rate": _metric(0.0505, 0.05),  # 1% worse — within noise
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "neutral"
    assert result["rollback_triggered"] is False


def test_evaluate_neutral_no_baselines():
    plan = {"metrics_to_watch": ["failed_rate", "throughput"], "rollback_triggers": []}
    observed = {
        "failed_rate": 0.07,   # scalar, no baseline
        "throughput": 95,      # scalar, no baseline
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "neutral"
    assert result["deviation_snapshot"]["failed_rate"]["verdict"] == "no_baseline"
    assert result["deviation_snapshot"]["throughput"]["verdict"] == "no_baseline"


def test_evaluate_degraded():
    plan = {"metrics_to_watch": ["failed_rate"], "rollback_triggers": []}
    observed = {
        "failed_rate": _metric(0.053, 0.05),  # 6% worse → degraded (above 5%, below 10%)
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "degraded"
    assert result["rollback_triggered"] is False
    assert result["deviation_snapshot"]["failed_rate"]["verdict"] == "degraded"


def test_evaluate_unstable():
    plan = {"metrics_to_watch": ["failed_rate"], "rollback_triggers": []}
    observed = {
        "failed_rate": _metric(0.12, 0.05),  # 140% worse → unstable
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "unstable"
    assert result["rollback_triggered"] is True
    assert result["rollback_reason"] is not None
    assert "failed_rate" in result["rollback_reason"]
    assert result["deviation_snapshot"]["failed_rate"]["verdict"] == "unstable"


def test_evaluate_rollback_triggered_at_threshold():
    plan = {"metrics_to_watch": ["failed_rate"], "rollback_triggers": []}
    # 12% worsening → clearly unstable (avoids float precision boundary at exactly 10%)
    observed = {"failed_rate": _metric(0.056, 0.05)}
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "unstable"
    assert result["rollback_triggered"] is True


def test_evaluate_higher_is_better_improved():
    plan = {"metrics_to_watch": ["throughput"], "rollback_triggers": []}
    observed = {
        "throughput": _metric(110, 100, direction="higher_is_better"),  # +10%
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "improved"
    assert result["deviation_snapshot"]["throughput"]["verdict"] == "improved"


def test_evaluate_higher_is_better_degraded():
    plan = {"metrics_to_watch": ["throughput"], "rollback_triggers": []}
    observed = {
        "throughput": _metric(88, 100, direction="higher_is_better"),  # -12% → unstable
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "unstable"
    assert result["rollback_triggered"] is True


def test_evaluate_missing_metric_skipped():
    plan = {
        "metrics_to_watch": ["failed_rate", "review_rate"],
        "rollback_triggers": [],
    }
    # Only provide one metric — review_rate is missing
    observed = {"failed_rate": _metric(0.03, 0.06)}
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    # Evaluation still works; improved based on the metric that exists
    assert result["evaluation_status"] == "improved"
    assert result["deviation_snapshot"]["review_rate"]["verdict"] == "missing"


def test_evaluate_zero_baseline_handled():
    plan = {"metrics_to_watch": ["failed_rate"], "rollback_triggers": []}
    observed = {"failed_rate": _metric(0.05, 0.0)}
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["deviation_snapshot"]["failed_rate"]["verdict"] == "zero_baseline"
    assert result["evaluation_status"] == "neutral"


def test_evaluate_empty_monitoring_plan():
    plan = {"metrics_to_watch": [], "rollback_triggers": []}
    observed = {"failed_rate": 0.05}
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "neutral"
    assert result["rollback_triggered"] is False


def test_evaluate_mixed_verdicts_degraded_wins():
    plan = {
        "metrics_to_watch": ["failed_rate", "throughput"],
        "rollback_triggers": [],
    }
    observed = {
        "failed_rate": _metric(0.03, 0.06),     # improved
        "throughput": _metric(85, 100, "higher_is_better"),  # -15% → unstable
    }
    result = evaluate_execution_outcome(
        monitoring_plan_snapshot=plan,
        observed_metrics_snapshot=observed,
    )
    assert result["evaluation_status"] == "unstable"
    assert result["rollback_triggered"] is True


# ---------------------------------------------------------------------------
# record_execution_outcome — persistence
# ---------------------------------------------------------------------------


def test_record_creates_new_outcome(db):
    req = _make_exec_request(id_=1001, tenant_id="tenant_rec")
    observed = {"failed_rate": _metric(0.03, 0.06)}

    outcome = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="success",
        observed_metrics_snapshot=observed,
    )
    db.commit()

    assert outcome.id is not None
    assert outcome.tenant_id == "tenant_rec"
    assert outcome.execution_request_id == 1001
    assert outcome.outcome_status == "success"
    assert outcome.evaluation_status == "improved"
    assert outcome.rollback_triggered is False
    assert outcome.change_id == req.change_id


def test_record_persists_deviation_snapshot(db):
    req = _make_exec_request(id_=1002, tenant_id="tenant_dev")
    observed = {"failed_rate": _metric(0.053, 0.05)}  # 6% worse → degraded

    outcome = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="partial",
        observed_metrics_snapshot=observed,
    )
    db.commit()

    deviation = json.loads(outcome.deviation_snapshot)
    assert "failed_rate" in deviation
    assert deviation["failed_rate"]["verdict"] == "degraded"


def test_record_sets_rollback_triggered(db):
    req = _make_exec_request(id_=1003, tenant_id="tenant_rlbk")
    observed = {"failed_rate": _metric(0.20, 0.05)}

    outcome = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="failed",
        observed_metrics_snapshot=observed,
    )
    db.commit()

    assert outcome.rollback_triggered is True
    assert outcome.rollback_reason is not None
    assert outcome.evaluation_status == "unstable"


def test_record_overwrites_existing_outcome(db):
    req = _make_exec_request(id_=1004, tenant_id="tenant_ow")

    # First recording — 6% worsening → degraded
    outcome1 = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="partial",
        observed_metrics_snapshot={"failed_rate": _metric(0.053, 0.05)},
    )
    db.commit()
    first_id = outcome1.id
    assert outcome1.evaluation_status == "degraded"

    # Re-record with improved metrics
    outcome2 = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="success",
        observed_metrics_snapshot={"failed_rate": _metric(0.03, 0.06)},
    )
    db.commit()

    assert outcome2.id == first_id
    assert outcome2.outcome_status == "success"
    assert outcome2.evaluation_status == "improved"


def test_record_invalid_outcome_status_raises(db):
    req = _make_exec_request(id_=1005, tenant_id="tenant_inv")
    with pytest.raises(ValueError, match="Invalid outcome_status"):
        record_execution_outcome(
            db,
            execution_request=req,
            outcome_status="unknown_value",
            observed_metrics_snapshot={},
        )


def test_record_persists_expected_metrics_snapshot(db):
    req = _make_exec_request(id_=1006, tenant_id="tenant_exp")
    expected = {"failed_rate": {"target": 0.04}}
    observed = {"failed_rate": _metric(0.03, 0.06)}

    outcome = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="success",
        observed_metrics_snapshot=observed,
        expected_metrics_snapshot=expected,
    )
    db.commit()

    stored = json.loads(outcome.expected_metrics_snapshot)
    assert stored["failed_rate"]["target"] == 0.04


def test_record_handles_missing_monitoring_plan(db):
    req = _make_exec_request(id_=1007, tenant_id="tenant_nmp")
    req.monitoring_plan_snapshot = None

    outcome = record_execution_outcome(
        db,
        execution_request=req,
        outcome_status="success",
        observed_metrics_snapshot={"failed_rate": 0.05},
    )
    db.commit()

    assert outcome.evaluation_status == "neutral"
    assert outcome.rollback_triggered is False


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_outcomes_are_tenant_isolated(db):
    req_a = _make_exec_request(id_=2001, tenant_id="tenant_iso_a")
    req_b = _make_exec_request(id_=2001, tenant_id="tenant_iso_b")

    outcome_a = record_execution_outcome(
        db,
        execution_request=req_a,
        outcome_status="success",
        observed_metrics_snapshot={"failed_rate": _metric(0.03, 0.06)},
    )
    outcome_b = record_execution_outcome(
        db,
        execution_request=req_b,
        outcome_status="failed",
        observed_metrics_snapshot={"failed_rate": _metric(0.20, 0.05)},
    )
    db.commit()

    assert outcome_a.id != outcome_b.id
    assert outcome_a.tenant_id == "tenant_iso_a"
    assert outcome_a.evaluation_status == "improved"
    assert outcome_b.tenant_id == "tenant_iso_b"
    assert outcome_b.evaluation_status == "unstable"
