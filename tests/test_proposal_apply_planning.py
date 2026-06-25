"""
tests/test_proposal_apply_planning.py

Unit tests for app/services/proposal_apply_planning.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test exercises one rule or status and asserts the output shape.
"""

from __future__ import annotations

import pytest

from app.services.proposal_apply_planning import (
    BLOCKED_FROM_PLANNING,
    PLANNED,
    REQUIRES_COMBINED_PLAN,
    compute_apply_planning,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SCOPE_TYPE = "pipeline"
SCOPE_ID = "construction"

CID = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
CID2 = "pipeline:paintly:fallback_path_hardening:fallback_validation_strictness"


def _change(
    change_id: str = CID,
    category: str = "confidence_threshold_tuning",
    change_type: str = "threshold_adjustment",
    risk_level: str = "medium",
    include_bounded_range: bool = True,
) -> dict:
    proposed_change: dict = {
        "direction": "decrease",
        "suggested_delta": 0.05,
    }
    if include_bounded_range:
        proposed_change["bounded_range"] = {"min": 0.50, "max": 0.90}

    return {
        "change_id": change_id,
        "category": category,
        "change_type": change_type,
        "target": {
            "parameter": "review_confidence_threshold",
            "scope_type": SCOPE_TYPE,
            "scope_id": SCOPE_ID,
        },
        "proposed_change": proposed_change,
        "approval_intent": {
            "requires_human_review": True,
            "risk_level": risk_level,
            "approval_type": "operator_confirmation",
        },
    }


def _readiness(change_id: str = CID, status: str = "approval_ready") -> dict:
    return {"change_id": change_id, "status": status, "severity": "low"}


def _staleness(change_id: str = CID, status: str = "fresh") -> dict:
    return {"change_id": change_id, "status": status, "severity": "low", "signals": []}


def _conflict(
    change_id: str = CID,
    severity: str = "high",
    conflict_type: str = "opposite_direction_conflict",
    proposal_ids: list[str] | None = None,
) -> dict:
    return {
        "conflict_id": "c1",
        "conflict_type": conflict_type,
        "severity": severity,
        "proposal_ids": proposal_ids or [change_id],
        "summary": "Conflict.",
    }


def _plan(
    changes: list[dict] | None = None,
    readiness: list[dict] | None = None,
    conflicts: list[dict] | None = None,
    staleness: list[dict] | None = None,
) -> dict:
    return compute_apply_planning(
        scope_type=SCOPE_TYPE,
        scope_id=SCOPE_ID,
        proposed_changes=changes or [],
        approval_readiness=readiness or [],
        conflicts=conflicts or [],
        staleness=staleness or [],
    )


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys_empty(self):
        result = _plan()
        assert set(result.keys()) == {
            "scope", "scope_id", "proposal_count",
            "planned_count", "combined_count", "blocked_count",
            "summary", "apply_plans",
        }

    def test_scope_fields(self):
        result = _plan()
        assert result["scope"] == SCOPE_TYPE
        assert result["scope_id"] == SCOPE_ID

    def test_empty_proposals(self):
        result = _plan()
        assert result["proposal_count"] == 0
        assert result["apply_plans"] == []
        assert result["summary"] == "No proposals to plan."

    def test_plan_entry_keys(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
        )
        entry = result["apply_plans"][0]
        assert set(entry.keys()) == {
            "change_id", "status", "severity", "summary",
            "execution_readiness", "preflight_checks", "dependencies",
            "execution_sequence", "rollback_plan", "safety_notes",
            "blocking_reasons", "recommendation",
        }

    def test_stable_output(self):
        change = _change()
        r1 = _plan(changes=[change], readiness=[_readiness()])
        r2 = _plan(changes=[change], readiness=[_readiness()])
        assert r1 == r2


# ---------------------------------------------------------------------------
# planned — happy path
# ---------------------------------------------------------------------------


class TestPlanned:
    def test_clean_proposal_is_planned(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness(status="approval_ready")],
            staleness=[_staleness(status="fresh")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == PLANNED
        assert entry["blocking_reasons"] == []
        assert entry["dependencies"] == []
        assert result["planned_count"] == 1
        assert result["blocked_count"] == 0
        assert result["combined_count"] == 0

    def test_severity_low_when_planned(self):
        result = _plan(changes=[_change()], readiness=[_readiness()])
        assert result["apply_plans"][0]["severity"] == "low"

    def test_execution_readiness_matches_status(self):
        result = _plan(changes=[_change()], readiness=[_readiness()])
        entry = result["apply_plans"][0]
        assert entry["execution_readiness"] == entry["status"]

    def test_summary_all_planned(self):
        result = _plan(changes=[_change()], readiness=[_readiness()])
        assert "guarded execution plan" in result["summary"]


# ---------------------------------------------------------------------------
# blocked_from_planning — approval readiness blocked
# ---------------------------------------------------------------------------


class TestBlockedByReadiness:
    def test_blocked_readiness_blocks_planning(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness(status="blocked")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("approval_readiness" in r for r in entry["blocking_reasons"])

    def test_blocked_with_warnings_readiness_does_not_block(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness(status="blocked_with_warnings")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == PLANNED

    def test_no_readiness_entry_does_not_block(self):
        result = _plan(changes=[_change()], readiness=[])
        entry = result["apply_plans"][0]
        assert entry["status"] == PLANNED


# ---------------------------------------------------------------------------
# blocked_from_planning — staleness
# ---------------------------------------------------------------------------


class TestBlockedByStaleness:
    def test_stale_blocks_planning(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            staleness=[_staleness(status="stale")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("stale" in r for r in entry["blocking_reasons"])

    def test_superseded_blocks_planning(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            staleness=[_staleness(status="superseded")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("superseded" in r for r in entry["blocking_reasons"])

    def test_aging_does_not_block(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            staleness=[_staleness(status="aging")],
        )
        assert result["apply_plans"][0]["status"] == PLANNED

    def test_fresh_does_not_block(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            staleness=[_staleness(status="fresh")],
        )
        assert result["apply_plans"][0]["status"] == PLANNED


# ---------------------------------------------------------------------------
# blocked_from_planning — high-severity conflict
# ---------------------------------------------------------------------------


class TestBlockedByHighConflict:
    def test_high_conflict_blocks_planning(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[_conflict(severity="high")],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("high-severity" in r for r in entry["blocking_reasons"])

    def test_low_conflict_does_not_block(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[_conflict(severity="low")],
        )
        assert result["apply_plans"][0]["status"] == PLANNED


# ---------------------------------------------------------------------------
# blocked_from_planning — missing fields
# ---------------------------------------------------------------------------


class TestBlockedByMissingFields:
    def test_missing_target_blocks(self):
        change = _change()
        change.pop("target")
        result = _plan(changes=[change], readiness=[_readiness()])
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("target" in r for r in entry["blocking_reasons"])

    def test_missing_proposed_change_blocks(self):
        change = _change()
        change.pop("proposed_change")
        result = _plan(changes=[change], readiness=[_readiness()])
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING

    def test_missing_bounded_range_blocks(self):
        result = _plan(
            changes=[_change(include_bounded_range=False)],
            readiness=[_readiness()],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == BLOCKED_FROM_PLANNING
        assert any("bounded_range" in r for r in entry["blocking_reasons"])


# ---------------------------------------------------------------------------
# requires_combined_plan
# ---------------------------------------------------------------------------


class TestRequiresCombinedPlan:
    def test_medium_same_target_overlap_requires_combined(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[
                _conflict(
                    severity="medium",
                    conflict_type="same_target_overlap",
                    proposal_ids=[CID, CID2],
                )
            ],
        )
        entry = result["apply_plans"][0]
        assert entry["status"] == REQUIRES_COMBINED_PLAN
        assert CID2 in entry["dependencies"]
        assert result["combined_count"] == 1

    def test_medium_policy_area_overlap_requires_combined(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[
                _conflict(
                    severity="medium",
                    conflict_type="policy_area_overlap",
                    proposal_ids=[CID, CID2],
                )
            ],
        )
        assert result["apply_plans"][0]["status"] == REQUIRES_COMBINED_PLAN

    def test_medium_high_risk_combination_requires_combined(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[
                _conflict(
                    severity="medium",
                    conflict_type="high_risk_combination",
                    proposal_ids=[CID, CID2],
                )
            ],
        )
        assert result["apply_plans"][0]["status"] == REQUIRES_COMBINED_PLAN

    def test_medium_other_conflict_type_does_not_require_combined(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness()],
            conflicts=[
                _conflict(
                    severity="medium",
                    conflict_type="opposite_direction_conflict",
                    proposal_ids=[CID, CID2],
                )
            ],
        )
        assert result["apply_plans"][0]["status"] == PLANNED

    def test_blocked_beats_combined_plan(self):
        result = _plan(
            changes=[_change()],
            readiness=[_readiness(status="blocked")],
            conflicts=[
                _conflict(
                    severity="medium",
                    conflict_type="same_target_overlap",
                    proposal_ids=[CID, CID2],
                )
            ],
        )
        assert result["apply_plans"][0]["status"] == BLOCKED_FROM_PLANNING


# ---------------------------------------------------------------------------
# Preflight checks per change_type
# ---------------------------------------------------------------------------


class TestPreflightChecks:
    def test_threshold_adjustment_preflight(self):
        result = _plan(changes=[_change(change_type="threshold_adjustment")], readiness=[_readiness()])
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("failed_rate" in c for c in checks)
        assert any("low_confidence_rate" in c for c in checks)
        assert any("threshold bounds" in c for c in checks)

    def test_pricing_guardrail_preflight(self):
        result = _plan(
            changes=[_change(change_type="pricing_guardrail_adjustment")],
            readiness=[_readiness()],
        )
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("underpricing" in c for c in checks)
        assert any("margin bounds" in c for c in checks)

    def test_validation_policy_preflight(self):
        result = _plan(
            changes=[_change(change_type="validation_policy_adjustment")],
            readiness=[_readiness()],
        )
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("upstream_input_quality" in c for c in checks)
        assert any("throughput" in c for c in checks)

    def test_fallback_policy_preflight(self):
        result = _plan(
            changes=[_change(change_type="fallback_policy_adjustment")],
            readiness=[_readiness()],
        )
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("fallback signal" in c for c in checks)

    def test_review_trigger_preflight(self):
        result = _plan(
            changes=[_change(change_type="review_trigger_adjustment")],
            readiness=[_readiness()],
        )
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("review pressure" in c for c in checks)
        assert any("failure metrics" in c for c in checks)

    def test_unknown_change_type_uses_default_preflight(self):
        result = _plan(
            changes=[_change(change_type="unknown_type")],
            readiness=[_readiness()],
        )
        checks = result["apply_plans"][0]["preflight_checks"]
        assert len(checks) > 0
        assert any("approval_readiness" in c for c in checks)

    def test_preflight_always_includes_base_checks(self):
        result = _plan(changes=[_change()], readiness=[_readiness()])
        checks = result["apply_plans"][0]["preflight_checks"]
        assert any("approval_readiness" in c for c in checks)
        assert any("high-severity conflicts" in c for c in checks)
        assert any("staleness" in c for c in checks)


# ---------------------------------------------------------------------------
# Rollback plans per change_type
# ---------------------------------------------------------------------------


class TestRollbackPlans:
    def test_threshold_rollback_present(self):
        result = _plan(changes=[_change(change_type="threshold_adjustment")], readiness=[_readiness()])
        rollback = result["apply_plans"][0]["rollback_plan"]
        assert len(rollback) > 0
        assert any("failed_rate" in r for r in rollback)

    def test_pricing_guardrail_rollback_present(self):
        result = _plan(
            changes=[_change(change_type="pricing_guardrail_adjustment")],
            readiness=[_readiness()],
        )
        rollback = result["apply_plans"][0]["rollback_plan"]
        assert any("win_rate" in r for r in rollback)

    def test_validation_policy_rollback_present(self):
        result = _plan(
            changes=[_change(change_type="validation_policy_adjustment")],
            readiness=[_readiness()],
        )
        rollback = result["apply_plans"][0]["rollback_plan"]
        assert any("throughput" in r for r in rollback)

    def test_fallback_policy_rollback_present(self):
        result = _plan(
            changes=[_change(change_type="fallback_policy_adjustment")],
            readiness=[_readiness()],
        )
        rollback = result["apply_plans"][0]["rollback_plan"]
        assert any("fallback" in r for r in rollback)

    def test_rollback_always_present(self):
        result = _plan(changes=[_change()], readiness=[_readiness()])
        assert len(result["apply_plans"][0]["rollback_plan"]) > 0


# ---------------------------------------------------------------------------
# Aggregate counters
# ---------------------------------------------------------------------------


class TestAggregateCounts:
    def test_counts_across_multiple_proposals(self):
        result = compute_apply_planning(
            scope_type=SCOPE_TYPE,
            scope_id=SCOPE_ID,
            proposed_changes=[
                _change(change_id=CID),
                _change(change_id=CID2, category="fallback_path_hardening"),
            ],
            approval_readiness=[
                _readiness(CID, "blocked"),
                _readiness(CID2, "approval_ready"),
            ],
            conflicts=[],
            staleness=[],
        )
        assert result["blocked_count"] == 1
        assert result["planned_count"] == 1
        assert result["proposal_count"] == 2

    def test_summary_reflects_mix(self):
        result = compute_apply_planning(
            scope_type=SCOPE_TYPE,
            scope_id=SCOPE_ID,
            proposed_changes=[_change(change_id=CID)],
            approval_readiness=[_readiness(CID, "blocked")],
            conflicts=[],
            staleness=[],
        )
        assert "blocked" in result["summary"]
