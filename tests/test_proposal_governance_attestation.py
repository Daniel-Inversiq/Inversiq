"""
tests/test_proposal_governance_attestation.py

Unit tests for the governance attestation service:
  app.services.proposal_governance_attestation.compute_governance_attestation

Tests cover:
  - change_id parse failures → unattestable
  - unknown scope_type → unattestable
  - scope not found in health summaries → unattestable
  - proposal not present in current governance output → unattestable
  - happy path with all governance layers returning valid statuses → attestable
  - governance chain reflecting blocked / stale / conflicted state
  - conflict_status aggregation (high vs medium)
  - staleness_status propagation
  - attestation_summary wording in valid / invalid cases

All governance layer functions are mocked so the test does not require a
populated database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.proposal_governance_attestation import (
    _unattestable,
    compute_governance_attestation,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TENANT = "tenant_attest_test"
CHANGE_ID = "pipeline:pipe_alpha:confidence_threshold_tuning:review_confidence_threshold"
SCOPE_TYPE = "pipeline"
SCOPE_ID = "pipe_alpha"

_MOCK_HEALTH = MagicMock()
_MOCK_HEALTH.pipeline_name = SCOPE_ID
_MOCK_HEALTH.health_status = "watch"
_MOCK_HEALTH.signal_counts = {"repeated_fallback": 2}

_BASE_CHANGE = {
    "change_id": CHANGE_ID,
    "category": "confidence_threshold_tuning",
    "title": "Lower review confidence threshold",
    "change_type": "threshold_adjustment",
    "target": {"parameter": "review_confidence_threshold", "scope_type": SCOPE_TYPE, "scope_id": SCOPE_ID},
    "proposed_change": {"direction": "decrease", "suggested_delta": 0.05},
}

_READINESS_READY = {
    "change_id": CHANGE_ID,
    "status": "approval_ready",
    "severity": "low",
    "summary": "Ready",
    "blocking_reasons": [],
    "warnings": [],
}

_READINESS_BLOCKED = {
    "change_id": CHANGE_ID,
    "status": "blocked",
    "severity": "high",
    "summary": "Blocked",
    "blocking_reasons": ["missing simulation preview"],
    "warnings": [],
}

_READINESS_BLOCKED_WITH_WARNINGS = {
    "change_id": CHANGE_ID,
    "status": "blocked_with_warnings",
    "severity": "medium",
    "summary": "Blocked with warnings",
    "blocking_reasons": [],
    "warnings": ["aging proposal"],
}

_PLAN_PLANNED = {
    "change_id": CHANGE_ID,
    "status": "planned",
    "severity": "low",
    "summary": "Planned",
}

_PLAN_REQUIRES_COMBINED = {
    "change_id": CHANGE_ID,
    "status": "requires_combined_plan",
    "severity": "medium",
    "summary": "Requires combined plan",
}

_PLAN_BLOCKED = {
    "change_id": CHANGE_ID,
    "status": "blocked_from_planning",
    "severity": "high",
    "summary": "Blocked from planning",
}

_STALENESS_FRESH = {"change_id": CHANGE_ID, "status": "fresh", "severity": "low"}
_STALENESS_STALE = {"change_id": CHANGE_ID, "status": "stale", "severity": "high"}
_STALENESS_AGING = {"change_id": CHANGE_ID, "status": "aging", "severity": "medium"}


def _db() -> MagicMock:
    return MagicMock()


def _patch_governance(
    *,
    health_items=None,
    changes=None,
    conflicts=None,
    staleness=None,
    approval_readiness=None,
    apply_plans=None,
):
    """Build a set of patches for the full governance chain."""
    if health_items is None:
        health_items = [_MOCK_HEALTH]
    if changes is None:
        changes = [_BASE_CHANGE]
    if conflicts is None:
        conflicts = []
    if staleness is None:
        staleness = [_STALENESS_FRESH]
    if approval_readiness is None:
        approval_readiness = [_READINESS_READY]
    if apply_plans is None:
        apply_plans = [_PLAN_PLANNED]

    return {
        "app.services.proposal_governance_attestation.pipeline_health_summaries": lambda *a, **kw: health_items,
        "app.services.proposal_governance_attestation.vertical_health_summaries": lambda *a, **kw: health_items,
        "app.services.proposal_governance_attestation.aggregate_metrics": lambda *a, **kw: {},
        "app.services.proposal_governance_attestation.compute_scope_trend": lambda *a, **kw: ({}, []),
        "app.services.proposal_governance_attestation.run_reasoning": lambda *a, **kw: {"reasoning": []},
        "app.services.proposal_governance_attestation.compute_control_suggestions": lambda *a, **kw: {"suggestions": []},
        "app.services.proposal_governance_attestation.compute_proposed_changes": lambda *a, **kw: {"proposed_changes": changes},
        "app.services.proposal_governance_attestation.detect_proposal_conflicts": lambda *a, **kw: {"conflicts": conflicts},
        "app.services.proposal_governance_attestation.detect_proposal_staleness": lambda *a, **kw: {"staleness": staleness},
        "app.services.proposal_governance_attestation.compute_simulation_preview": lambda *a, **kw: {"previews": []},
        "app.services.proposal_governance_attestation.evaluate_proposal_approval_readiness": lambda *a, **kw: {"approval_readiness": approval_readiness},
        "app.services.proposal_governance_attestation.compute_apply_planning": lambda *a, **kw: {"apply_plans": apply_plans},
        "app.services.proposal_governance_attestation._load_review_states": lambda *a, **kw: {},
    }


def _run_with_patches(patches: dict, *, tenant_id=TENANT, change_id=CHANGE_ID) -> dict:
    with patch.multiple("app.services.proposal_governance_attestation", **{
        k.split(".")[-1]: v for k, v in patches.items()
    }):
        return compute_governance_attestation(_db(), tenant_id=tenant_id, change_id=change_id)


# ---------------------------------------------------------------------------
# Unattestable: parse / format failures
# ---------------------------------------------------------------------------


class TestUnattestableParsing:
    def test_missing_parts_returns_unattestable(self):
        result = compute_governance_attestation(
            _db(), tenant_id=TENANT, change_id="pipeline:scope_only"
        )
        assert result["attestable"] is False
        assert "scope_type:scope_id:category:parameter" in result["attestation_summary"]

    def test_too_many_colons_is_fine(self):
        # 4-part split with maxsplit=3 means extra colons in parameter are OK
        # "pipeline:scope:cat:param:extra" splits to 4 parts with param="param:extra"
        cid = "pipeline:scope:cat:param:extra"
        patches = _patch_governance(changes=[], health_items=[_MOCK_HEALTH])
        # health lookup fails because scope_id is "scope" not SCOPE_ID
        mock_health = MagicMock()
        mock_health.pipeline_name = "scope"
        mock_health.health_status = "healthy"
        mock_health.signal_counts = {}
        patches_adj = _patch_governance(
            health_items=[mock_health],
            changes=[],  # change not found
        )
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches_adj.items()},
        ):
            result = compute_governance_attestation(_db(), tenant_id=TENANT, change_id=cid)
        assert result["attestable"] is False
        assert "not present" in result["attestation_summary"]

    def test_unknown_scope_type_returns_unattestable(self):
        result = compute_governance_attestation(
            _db(), tenant_id=TENANT, change_id="unknown:scope:cat:param"
        )
        assert result["attestable"] is False
        assert "Unknown scope_type" in result["attestation_summary"]

    def test_unattestable_helper_shape(self):
        result = _unattestable("cid", "test reason")
        assert result["attestable"] is False
        assert result["change_id"] == "cid"
        assert result["attestation_summary"] == "test reason"
        assert result["approval_readiness_status"] is None
        assert result["apply_planning_status"] is None
        assert result["conflict_status"] is None
        assert result["staleness_status"] is None
        assert result["attested_at"] is None


# ---------------------------------------------------------------------------
# Unattestable: scope not found
# ---------------------------------------------------------------------------


class TestUnattestableScopeNotFound:
    def test_pipeline_scope_not_in_health_summaries(self):
        other_health = MagicMock()
        other_health.pipeline_name = "other_pipe"
        patches = _patch_governance(health_items=[other_health])
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            result = compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )
        assert result["attestable"] is False
        assert "not found in current health summaries" in result["attestation_summary"]

    def test_vertical_scope_not_in_health_summaries(self):
        other_health = MagicMock()
        other_health.vertical_id = "other_vertical"
        patches = _patch_governance(health_items=[other_health])
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            result = compute_governance_attestation(
                _db(),
                tenant_id=TENANT,
                change_id="vertical:some_vertical:cat:param",
            )
        assert result["attestable"] is False
        assert "not found in current health summaries" in result["attestation_summary"]

    def test_empty_health_summaries_returns_unattestable(self):
        patches = _patch_governance(health_items=[])
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            result = compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )
        assert result["attestable"] is False


# ---------------------------------------------------------------------------
# Unattestable: change not present in governance output
# ---------------------------------------------------------------------------


class TestUnattestableChangeNotFound:
    def test_change_not_in_proposed_changes_output(self):
        other_change = {**_BASE_CHANGE, "change_id": "pipeline:pipe_alpha:other_cat:other_param"}
        patches = _patch_governance(changes=[other_change])
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            result = compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )
        assert result["attestable"] is False
        assert "not present in the current governance output" in result["attestation_summary"]

    def test_empty_proposed_changes_returns_unattestable(self):
        patches = _patch_governance(changes=[])
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            result = compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )
        assert result["attestable"] is False


# ---------------------------------------------------------------------------
# Happy path: attestable with approval_ready + planned
# ---------------------------------------------------------------------------


class TestAttestableHappyPath:
    def _run(self, **overrides) -> dict:
        patches = _patch_governance(**overrides)
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            return compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )

    def test_attestable_true(self):
        result = self._run()
        assert result["attestable"] is True

    def test_change_id_echoed(self):
        result = self._run()
        assert result["change_id"] == CHANGE_ID

    def test_scope_type_and_id(self):
        result = self._run()
        assert result["scope_type"] == "pipeline"
        assert result["scope_id"] == SCOPE_ID

    def test_approval_readiness_status_approval_ready(self):
        result = self._run()
        assert result["approval_readiness_status"] == "approval_ready"

    def test_apply_planning_status_planned(self):
        result = self._run()
        assert result["apply_planning_status"] == "planned"

    def test_staleness_fresh(self):
        result = self._run()
        assert result["staleness_status"] == "fresh"

    def test_no_conflicts(self):
        result = self._run()
        assert result["conflict_status"]["has_high_conflict"] is False
        assert result["conflict_status"]["has_medium_conflict"] is False

    def test_attested_at_is_iso_string(self):
        result = self._run()
        assert result["attested_at"] is not None
        # Should parse as ISO datetime without error
        datetime.fromisoformat(result["attested_at"])

    def test_governance_valid_summary(self):
        result = self._run()
        assert "governance-valid" in result["attestation_summary"]


# ---------------------------------------------------------------------------
# Blocked scenarios
# ---------------------------------------------------------------------------


class TestAttestableBlocked:
    def _run(self, **overrides) -> dict:
        patches = _patch_governance(**overrides)
        with patch.multiple(
            "app.services.proposal_governance_attestation",
            **{k.split(".")[-1]: v for k, v in patches.items()},
        ):
            return compute_governance_attestation(
                _db(), tenant_id=TENANT, change_id=CHANGE_ID
            )

    def test_blocked_readiness_propagated(self):
        result = self._run(approval_readiness=[_READINESS_BLOCKED])
        assert result["attestable"] is True
        assert result["approval_readiness_status"] == "blocked"
        assert "approval_readiness" in result["attestation_summary"]

    def test_blocked_with_warnings_readiness_propagated(self):
        result = self._run(approval_readiness=[_READINESS_BLOCKED_WITH_WARNINGS])
        assert result["approval_readiness_status"] == "blocked_with_warnings"
        assert "approval_readiness" in result["attestation_summary"]

    def test_requires_combined_plan_propagated(self):
        result = self._run(apply_plans=[_PLAN_REQUIRES_COMBINED])
        assert result["apply_planning_status"] == "requires_combined_plan"
        assert "apply_planning" in result["attestation_summary"]

    def test_blocked_from_planning_propagated(self):
        result = self._run(apply_plans=[_PLAN_BLOCKED])
        assert result["apply_planning_status"] == "blocked_from_planning"

    def test_stale_propagated(self):
        result = self._run(staleness=[_STALENESS_STALE])
        assert result["staleness_status"] == "stale"
        assert "stale" in result["attestation_summary"]

    def test_aging_is_still_valid_for_summary(self):
        result = self._run(staleness=[_STALENESS_AGING])
        assert result["staleness_status"] == "aging"
        # aging is governance-valid when readiness + planning are both OK
        assert "governance-valid" in result["attestation_summary"]

    def test_high_conflict_propagated(self):
        conflict = {
            "conflict_id": "test_conflict",
            "severity": "high",
            "proposal_ids": [CHANGE_ID],
            "conflict_type": "opposite_direction_conflict",
            "summary": "Conflict",
        }
        result = self._run(conflicts=[conflict])
        assert result["conflict_status"]["has_high_conflict"] is True
        assert "high-severity conflict" in result["attestation_summary"]

    def test_medium_conflict_not_in_summary_but_flagged(self):
        conflict = {
            "conflict_id": "test_conflict",
            "severity": "medium",
            "proposal_ids": [CHANGE_ID],
            "conflict_type": "policy_area_overlap",
            "summary": "Medium conflict",
        }
        result = self._run(conflicts=[conflict])
        assert result["conflict_status"]["has_medium_conflict"] is True
        # Medium conflict alone doesn't produce "not governance-valid" wording
        # (only high conflict does); governance_valid logic only blocks on high
        assert result["conflict_status"]["has_high_conflict"] is False

    def test_conflict_not_involving_this_change_is_ignored(self):
        conflict = {
            "conflict_id": "test_conflict",
            "severity": "high",
            "proposal_ids": ["some_other_change_id"],
            "conflict_type": "same_target_overlap",
            "summary": "Other conflict",
        }
        result = self._run(conflicts=[conflict])
        assert result["conflict_status"]["has_high_conflict"] is False

    def test_missing_readiness_entry_defaults_to_blocked(self):
        # Readiness list returns entry for a different change_id
        other_readiness = {**_READINESS_READY, "change_id": "other:change"}
        result = self._run(approval_readiness=[other_readiness])
        assert result["approval_readiness_status"] == "blocked"

    def test_missing_plan_entry_defaults_to_blocked_from_planning(self):
        other_plan = {**_PLAN_PLANNED, "change_id": "other:change"}
        result = self._run(apply_plans=[other_plan])
        assert result["apply_planning_status"] == "blocked_from_planning"

    def test_missing_staleness_entry_defaults_to_unknown(self):
        other_staleness = {**_STALENESS_FRESH, "change_id": "other:change"}
        result = self._run(staleness=[other_staleness])
        assert result["staleness_status"] == "unknown"

    def test_multiple_blocking_reasons_all_appear_in_summary(self):
        result = self._run(
            approval_readiness=[_READINESS_BLOCKED],
            apply_plans=[_PLAN_BLOCKED],
            staleness=[_STALENESS_STALE],
        )
        summary = result["attestation_summary"]
        assert "approval_readiness" in summary
        assert "apply_planning" in summary
        assert "stale" in summary
