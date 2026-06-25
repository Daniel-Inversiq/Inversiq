"""
tests/test_proposal_approval_readiness.py

Unit tests for app/services/proposal_approval_readiness.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test exercises one rule or status and asserts the output shape.
"""

from __future__ import annotations

import pytest

from app.services.proposal_approval_readiness import (
    APPROVAL_READY,
    BLOCKED,
    BLOCKED_WITH_WARNINGS,
    evaluate_proposal_approval_readiness,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SCOPE_TYPE = "pipeline"
SCOPE_ID = "construction"


def _change(
    change_id: str = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold",
    category: str = "confidence_threshold_tuning",
    parameter: str = "review_confidence_threshold",
    risk_level: str = "medium",
) -> dict:
    return {
        "change_id": change_id,
        "category": category,
        "change_type": "threshold_adjustment",
        "target": {
            "parameter": parameter,
            "scope_type": SCOPE_TYPE,
            "scope_id": SCOPE_ID,
        },
        "proposed_change": {
            "direction": "decrease",
            "suggested_delta": 0.05,
            "bounded_range": {"min": 0.50, "max": 0.90},
        },
        "approval_intent": {
            "requires_human_review": True,
            "risk_level": risk_level,
            "approval_type": "operator_confirmation",
        },
    }


def _evaluate(
    changes: list[dict] | None = None,
    review_states: dict | None = None,
    conflicts: list[dict] | None = None,
    staleness: list[dict] | None = None,
    reasoning_categories: list[str] | None = None,
    control_categories: list[str] | None = None,
    simulation_previews: list[dict] | None = None,
) -> dict:
    return evaluate_proposal_approval_readiness(
        scope_type=SCOPE_TYPE,
        scope_id=SCOPE_ID,
        proposed_changes=changes or [],
        review_states=review_states or {},
        conflicts=conflicts or [],
        staleness=staleness or [],
        reasoning_categories=reasoning_categories if reasoning_categories is not None else ["confidence_threshold_mismatch"],
        control_categories=control_categories if control_categories is not None else ["confidence_threshold_tuning"],
        simulation_previews=simulation_previews or [],
    )


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys_empty(self):
        result = _evaluate()
        assert set(result.keys()) == {
            "scope", "scope_id", "proposal_count",
            "blocked_count", "warnings_count", "ready_count",
            "summary", "approval_readiness",
        }

    def test_scope_fields(self):
        result = _evaluate()
        assert result["scope"] == SCOPE_TYPE
        assert result["scope_id"] == SCOPE_ID

    def test_empty_proposals(self):
        result = _evaluate()
        assert result["proposal_count"] == 0
        assert result["approval_readiness"] == []
        assert result["summary"] == "No proposals to evaluate."

    def test_readiness_entry_keys(self):
        result = _evaluate(changes=[_change()])
        entry = result["approval_readiness"][0]
        assert set(entry.keys()) == {
            "change_id", "status", "severity", "summary",
            "blocking_reasons", "warnings", "required_actions", "recommendation",
        }

    def test_stable_output(self):
        change = _change()
        r1 = _evaluate(changes=[change])
        r2 = _evaluate(changes=[change])
        assert r1 == r2


# ---------------------------------------------------------------------------
# approval_ready
# ---------------------------------------------------------------------------


class TestApprovalReady:
    def test_clean_proposal_is_ready(self):
        result = _evaluate(changes=[_change()])
        entry = result["approval_readiness"][0]
        assert entry["status"] == APPROVAL_READY
        assert entry["blocking_reasons"] == []
        assert entry["warnings"] == []
        assert result["ready_count"] == 1
        assert result["blocked_count"] == 0
        assert result["warnings_count"] == 0

    def test_summary_all_ready(self):
        result = _evaluate(changes=[_change()])
        assert "approval-ready" in result["summary"]

    def test_severity_low_when_ready(self):
        result = _evaluate(changes=[_change()])
        assert result["approval_readiness"][0]["severity"] == "low"


# ---------------------------------------------------------------------------
# blocked — review state
# ---------------------------------------------------------------------------


class TestBlockedByReviewState:
    def test_rejected_state_blocks(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            review_states={cid: {"status": "rejected", "created_at": None, "updated_at": None, "persisted": True}},
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("rejected" in r for r in entry["blocking_reasons"])

    def test_archived_state_blocks(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            review_states={cid: {"status": "archived", "created_at": None, "updated_at": None, "persisted": True}},
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("archived" in r for r in entry["blocking_reasons"])

    def test_pending_state_does_not_block(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            review_states={cid: {"status": "pending", "created_at": None, "updated_at": None, "persisted": True}},
        )
        assert result["approval_readiness"][0]["status"] == APPROVAL_READY


# ---------------------------------------------------------------------------
# blocked — staleness
# ---------------------------------------------------------------------------


class TestBlockedByStaleness:
    def _stale_entry(self, change_id: str, status: str) -> dict:
        return {"change_id": change_id, "status": status, "severity": "high", "signals": []}

    def test_stale_blocks(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            staleness=[self._stale_entry(cid, "stale")],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("stale" in r for r in entry["blocking_reasons"])
        assert any("Regenerate" in a for a in entry["required_actions"])

    def test_superseded_blocks(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            staleness=[self._stale_entry(cid, "superseded")],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("superseded" in r for r in entry["blocking_reasons"])
        assert any("newer" in a for a in entry["required_actions"])

    def test_fresh_does_not_block(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            staleness=[self._stale_entry(cid, "fresh")],
        )
        assert result["approval_readiness"][0]["status"] == APPROVAL_READY


# ---------------------------------------------------------------------------
# blocked — high-severity conflict
# ---------------------------------------------------------------------------


class TestBlockedByConflict:
    def _conflict(self, change_id: str, severity: str = "high") -> dict:
        return {
            "conflict_id": "c1",
            "conflict_type": "opposite_direction_conflict",
            "severity": severity,
            "proposal_ids": [change_id],
            "summary": "Conflicting directions.",
        }

    def test_high_conflict_blocks(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            conflicts=[self._conflict(cid, "high")],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("high-severity" in r for r in entry["blocking_reasons"])
        assert any("conflicts" in a for a in entry["required_actions"])

    def test_low_conflict_does_not_block(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            conflicts=[self._conflict(cid, "low")],
        )
        # low conflict is not a hard-block and not a warning — no rule for low severity
        assert result["approval_readiness"][0]["status"] == APPROVAL_READY


# ---------------------------------------------------------------------------
# blocked — control category missing
# ---------------------------------------------------------------------------


class TestBlockedByMissingCategory:
    def test_missing_control_category_blocks(self):
        result = _evaluate(
            changes=[_change(category="confidence_threshold_tuning")],
            control_categories=["fallback_path_hardening"],  # does not include proposal category
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("no longer active" in r for r in entry["blocking_reasons"])

    def test_empty_reasoning_blocks(self):
        result = _evaluate(
            changes=[_change()],
            reasoning_categories=[],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("No active reasoning" in r for r in entry["blocking_reasons"])

    def test_present_control_category_does_not_block(self):
        result = _evaluate(
            changes=[_change(category="confidence_threshold_tuning")],
            control_categories=["confidence_threshold_tuning"],
        )
        assert result["approval_readiness"][0]["status"] == APPROVAL_READY


# ---------------------------------------------------------------------------
# blocked — missing fields (defensive)
# ---------------------------------------------------------------------------


class TestBlockedByMissingFields:
    def test_missing_target_blocks(self):
        change = _change()
        change.pop("target")
        result = _evaluate(changes=[change])
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert any("target" in r for r in entry["blocking_reasons"])

    def test_missing_proposed_change_blocks(self):
        change = _change()
        change.pop("proposed_change")
        result = _evaluate(changes=[change])
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED


# ---------------------------------------------------------------------------
# blocked_with_warnings
# ---------------------------------------------------------------------------


class TestBlockedWithWarnings:
    def _aging_entry(self, change_id: str) -> dict:
        return {"change_id": change_id, "status": "aging", "severity": "medium", "signals": []}

    def test_aging_staleness_warns(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            staleness=[self._aging_entry(cid)],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED_WITH_WARNINGS
        assert any("aging" in w for w in entry["warnings"])
        assert entry["severity"] == "medium"

    def test_medium_conflict_warns(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        conflict = {
            "conflict_id": "c1",
            "conflict_type": "policy_area_overlap",
            "severity": "medium",
            "proposal_ids": [cid],
            "summary": "Policy area overlap.",
        }
        result = _evaluate(
            changes=[_change(change_id=cid)],
            conflicts=[conflict],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED_WITH_WARNINGS
        assert any("medium-severity" in w for w in entry["warnings"])

    def test_low_simulation_confidence_warns(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        preview = {"category": "confidence_threshold_tuning", "confidence": "low"}
        result = _evaluate(
            changes=[_change(change_id=cid)],
            simulation_previews=[preview],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED_WITH_WARNINGS
        assert any("low" in w for w in entry["warnings"])

    def test_high_risk_warns(self):
        result = _evaluate(changes=[_change(risk_level="high")])
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED_WITH_WARNINGS
        assert any("high" in w for w in entry["warnings"])

    def test_medium_confidence_does_not_warn(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        preview = {"category": "confidence_threshold_tuning", "confidence": "medium"}
        result = _evaluate(
            changes=[_change(change_id=cid)],
            simulation_previews=[preview],
        )
        assert result["approval_readiness"][0]["status"] == APPROVAL_READY


# ---------------------------------------------------------------------------
# Priority: blocked beats warnings
# ---------------------------------------------------------------------------


class TestStatusPriority:
    def test_blocked_beats_warnings(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        aging = {"change_id": cid, "status": "aging", "severity": "medium", "signals": []}
        result = _evaluate(
            changes=[_change(change_id=cid)],
            review_states={cid: {"status": "rejected", "created_at": None, "updated_at": None, "persisted": True}},
            staleness=[aging],
        )
        entry = result["approval_readiness"][0]
        assert entry["status"] == BLOCKED
        assert len(entry["blocking_reasons"]) >= 1
        assert len(entry["warnings"]) >= 1  # aging warning still recorded


# ---------------------------------------------------------------------------
# Aggregate counters
# ---------------------------------------------------------------------------


class TestAggregateCounts:
    def test_counts_across_multiple_proposals(self):
        cid1 = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        cid2 = "pipeline:paintly:fallback_path_hardening:fallback_validation_strictness"

        result = evaluate_proposal_approval_readiness(
            scope_type=SCOPE_TYPE,
            scope_id=SCOPE_ID,
            proposed_changes=[_change(change_id=cid1), _change(change_id=cid2, category="fallback_path_hardening")],
            review_states={cid1: {"status": "rejected", "created_at": None, "updated_at": None, "persisted": True}},
            conflicts=[],
            staleness=[],
            reasoning_categories=["confidence_threshold_mismatch"],
            control_categories=["confidence_threshold_tuning", "fallback_path_hardening"],
            simulation_previews=[],
        )

        assert result["blocked_count"] == 1
        assert result["ready_count"] == 1
        assert result["proposal_count"] == 2

    def test_summary_reflects_mix(self):
        cid = "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"
        result = _evaluate(
            changes=[_change(change_id=cid)],
            review_states={cid: {"status": "rejected", "created_at": None, "updated_at": None, "persisted": True}},
        )
        assert "blocked" in result["summary"]
