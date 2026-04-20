"""
tests/test_proposal_conflicts.py

Unit tests for app/services/proposal_conflicts.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test exercises one conflict category and asserts the output shape.
"""

from __future__ import annotations

import pytest

from app.services.proposal_conflicts import detect_proposal_conflicts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _change(
    change_id: str,
    change_type: str = "threshold_adjustment",
    parameter: str = "review_confidence_threshold",
    direction: str = "decrease",
    scope_type: str = "pipeline",
    scope_id: str = "paintly",
    risk_level: str = "medium",
) -> dict:
    return {
        "change_id": change_id,
        "category": "confidence_threshold_tuning",
        "change_type": change_type,
        "target": {
            "parameter": parameter,
            "scope_type": scope_type,
            "scope_id": scope_id,
        },
        "proposed_change": {
            "direction": direction,
            "suggested_delta": 0.05,
            "bounded_range": {"min": 0.50, "max": 0.90},
        },
        "approval_intent": {
            "requires_human_review": True,
            "risk_level": risk_level,
            "approval_type": "operator_confirmation",
        },
    }


def _detect(changes: list[dict], scope_type: str = "pipeline", scope_id: str = "paintly") -> dict:
    return detect_proposal_conflicts(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
    )


# ---------------------------------------------------------------------------
# No-conflict baseline
# ---------------------------------------------------------------------------


def test_no_conflicts_empty_list():
    result = _detect([])
    assert result["conflict_count"] == 0
    assert result["conflicts"] == []
    assert result["summary"] == "No proposal conflicts detected."


def test_no_conflicts_single_change():
    result = _detect([_change("pipeline:paintly:ct:p")])
    assert result["conflict_count"] == 0
    assert result["conflicts"] == []


def test_no_conflicts_distinct_parameters():
    # Use low-risk changes on unrelated parameters with no shared policy area
    c1 = _change("id1", parameter="review_confidence_threshold", risk_level="low")
    c2 = _change("id2", parameter="unrelated_param", change_type="validation_policy_adjustment", risk_level="low")
    result = _detect([c1, c2])
    assert result["conflict_count"] == 0


# ---------------------------------------------------------------------------
# same_target_overlap
# ---------------------------------------------------------------------------


def test_same_target_overlap_detected():
    c1 = _change("pipeline:paintly:ct_tuning:rct", parameter="review_confidence_threshold")
    c2 = _change("pipeline:paintly:rt_narrowing:rct", parameter="review_confidence_threshold")
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "same_target_overlap" in types

    conflict = next(c for c in result["conflicts"] if c["conflict_type"] == "same_target_overlap")
    assert set(conflict["proposal_ids"]) == {c1["change_id"], c2["change_id"]}
    assert conflict["severity"] == "medium"
    assert conflict["target"]["parameter"] == "review_confidence_threshold"


def test_same_target_overlap_stable_conflict_id():
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")
    r1 = _detect([c1, c2])
    r2 = _detect([c1, c2])

    ids1 = {c["conflict_id"] for c in r1["conflicts"]}
    ids2 = {c["conflict_id"] for c in r2["conflicts"]}
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# opposite_direction_conflict
# ---------------------------------------------------------------------------


def test_opposite_direction_conflict_detected():
    c1 = _change("id_inc", parameter="review_confidence_threshold", direction="increase")
    c2 = _change("id_dec", parameter="review_confidence_threshold", direction="decrease")
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "opposite_direction_conflict" in types

    conflict = next(c for c in result["conflicts"] if c["conflict_type"] == "opposite_direction_conflict")
    assert conflict["severity"] == "high"
    assert set(conflict["proposal_ids"]) == {"id_inc", "id_dec"}


def test_opposite_direction_conflict_suppresses_same_target_overlap():
    """When opposite_direction_conflict covers the same pair, same_target_overlap is suppressed."""
    c1 = _change("id_inc", parameter="review_confidence_threshold", direction="increase")
    c2 = _change("id_dec", parameter="review_confidence_threshold", direction="decrease")
    result = _detect([c1, c2])

    types = [c["conflict_type"] for c in result["conflicts"]]
    assert "opposite_direction_conflict" in types
    assert "same_target_overlap" not in types


def test_same_direction_does_not_trigger_opposite():
    c1 = _change("id1", parameter="review_confidence_threshold", direction="decrease")
    c2 = _change("id2", parameter="review_confidence_threshold", direction="decrease")
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "opposite_direction_conflict" not in types


# ---------------------------------------------------------------------------
# duplicate_proposal
# ---------------------------------------------------------------------------


def test_duplicate_proposal_detected():
    c1 = _change("id_a", change_type="threshold_adjustment", parameter="review_confidence_threshold")
    c2 = _change("id_b", change_type="threshold_adjustment", parameter="review_confidence_threshold")
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "duplicate_proposal" in types

    conflict = next(c for c in result["conflicts"] if c["conflict_type"] == "duplicate_proposal")
    assert conflict["severity"] == "medium"
    assert set(conflict["proposal_ids"]) == {"id_a", "id_b"}


def test_same_change_id_not_duplicate():
    """Identical change_id should not trigger duplicate detection."""
    c = _change("same_id")
    result = _detect([c, c])
    types = {conf["conflict_type"] for conf in result["conflicts"]}
    assert "duplicate_proposal" not in types


# ---------------------------------------------------------------------------
# policy_area_overlap
# ---------------------------------------------------------------------------


def test_policy_area_overlap_detected():
    c1 = _change(
        "id_a",
        change_type="review_trigger_adjustment",
        parameter="review_confidence_threshold",
    )
    c2 = _change(
        "id_b",
        change_type="review_trigger_adjustment",
        parameter="review_trigger_threshold",
    )
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "policy_area_overlap" in types

    conflict = next(c for c in result["conflicts"] if c["conflict_type"] == "policy_area_overlap")
    assert conflict["severity"] in ("low", "medium")
    assert conflict["target"]["parameter"] == "review_policy"


def test_policy_area_overlap_requires_distinct_parameters():
    """Same parameter in the same policy area should not trigger policy_area_overlap."""
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")
    result = _detect([c1, c2])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "policy_area_overlap" not in types


# ---------------------------------------------------------------------------
# high_risk_combination
# ---------------------------------------------------------------------------


def test_high_risk_combination_with_pricing():
    pricing = _change(
        "id_pricing",
        change_type="pricing_guardrail_adjustment",
        parameter="margin_guardrail",
        risk_level="high",
    )
    fallback = _change(
        "id_fallback",
        change_type="fallback_policy_adjustment",
        parameter="fallback_threshold",
        risk_level="medium",
    )
    result = _detect([pricing, fallback])

    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "high_risk_combination" in types

    conflict = next(c for c in result["conflicts"] if c["conflict_type"] == "high_risk_combination")
    assert conflict["severity"] == "high"


def test_high_risk_combination_single_high_risk_no_conflict():
    pricing = _change(
        "id_pricing",
        change_type="pricing_guardrail_adjustment",
        parameter="margin_guardrail",
        risk_level="high",
    )
    result = _detect([pricing])
    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "high_risk_combination" not in types


def test_high_risk_combination_low_risk_only_no_conflict():
    c1 = _change("id1", change_type="threshold_adjustment", risk_level="low")
    c2 = _change("id2", change_type="review_trigger_adjustment", parameter="review_trigger_threshold", risk_level="low")
    result = _detect([c1, c2])
    types = {c["conflict_type"] for c in result["conflicts"]}
    assert "high_risk_combination" not in types


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------


def test_conflicts_ordered_by_severity_high_first():
    pricing = _change("id_p", change_type="pricing_guardrail_adjustment", parameter="margin_guardrail", risk_level="high")
    fallback = _change("id_f", change_type="fallback_policy_adjustment", parameter="fallback_threshold", risk_level="medium")
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")

    result = _detect([pricing, fallback, c1, c2])
    severities = [c["severity"] for c in result["conflicts"]]
    order = {"high": 2, "medium": 1, "low": 0}
    scores = [order[s] for s in severities]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


def test_output_shape():
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")
    result = _detect([c1, c2])

    assert "scope" in result
    assert "scope_id" in result
    assert "proposal_count" in result
    assert "conflict_count" in result
    assert "summary" in result
    assert "conflicts" in result

    assert result["scope"] == "pipeline"
    assert result["scope_id"] == "paintly"
    assert result["proposal_count"] == 2


def test_conflict_object_shape():
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")
    result = _detect([c1, c2])

    conflict = result["conflicts"][0]
    for key in ("conflict_id", "conflict_type", "severity", "proposal_ids", "target", "summary", "reason", "recommendation"):
        assert key in conflict, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Tenant isolation — scope_id is part of conflict_id
# ---------------------------------------------------------------------------


def test_conflict_id_includes_scope():
    c1 = _change("id_a", parameter="review_confidence_threshold")
    c2 = _change("id_b", parameter="review_confidence_threshold")

    r_paintly = _detect([c1, c2], scope_id="paintly")
    r_other = _detect([c1, c2], scope_id="other_pipe")

    ids_paintly = {c["conflict_id"] for c in r_paintly["conflicts"]}
    ids_other = {c["conflict_id"] for c in r_other["conflicts"]}
    assert ids_paintly.isdisjoint(ids_other)


# ---------------------------------------------------------------------------
# no_action_proposed changes are excluded
# ---------------------------------------------------------------------------


def test_no_action_proposed_excluded():
    no_action = {
        "change_id": "id_no_action",
        "change_type": "no_action_proposed",
        "target": {"parameter": "review_confidence_threshold", "scope_type": "pipeline", "scope_id": "paintly"},
        "proposed_change": {"direction": "none", "suggested_delta": None, "bounded_range": None},
        "approval_intent": {"risk_level": "low"},
    }
    c1 = _change("id_a", parameter="review_confidence_threshold")

    result = _detect([no_action, c1])
    assert result["conflict_count"] == 0
