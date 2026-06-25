"""
tests/test_proposal_staleness.py

Unit tests for app/services/proposal_staleness.py.

All tests operate on plain dicts and fixed datetimes — no DB, no HTTP.
Each test exercises one staleness category or rule and asserts the output shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.proposal_staleness import (
    AGING_DAYS,
    STALE_DAYS,
    detect_proposal_staleness,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)


def _change(
    change_id: str = "pipeline:paintly:ct_tuning:review_confidence_threshold",
    category: str = "confidence_threshold_tuning",
    parameter: str = "review_confidence_threshold",
    scope_type: str = "pipeline",
    scope_id: str = "construction",
) -> dict:
    return {
        "change_id": change_id,
        "category": category,
        "change_type": "threshold_adjustment",
        "target": {
            "parameter": parameter,
            "scope_type": scope_type,
            "scope_id": scope_id,
        },
        "proposed_change": {
            "direction": "decrease",
            "suggested_delta": 0.05,
            "bounded_range": {"min": 0.50, "max": 0.90},
        },
        "approval_intent": {
            "requires_human_review": True,
            "risk_level": "medium",
            "approval_type": "operator_confirmation",
        },
    }


def _review_state(
    *,
    status: str = "pending",
    created_at: datetime,
    updated_at: datetime | None = None,
    persisted: bool = True,
) -> dict:
    return {
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "persisted": persisted,
    }


def _detect(
    changes: list[dict],
    review_states: dict | None = None,
    reasoning_categories: list[str] | None = None,
    control_categories: list[str] | None = None,
    scope_type: str = "pipeline",
    scope_id: str = "construction",
) -> dict:
    return detect_proposal_staleness(
        scope_type=scope_type,
        scope_id=scope_id,
        proposed_changes=changes,
        review_states=review_states if review_states is not None else {},
        current_reasoning_categories=reasoning_categories if reasoning_categories is not None else [],
        current_control_categories=control_categories if control_categories is not None else ["confidence_threshold_tuning"],
        now=NOW,
    )


def _annotation_for(result: dict, change_id: str) -> dict:
    for a in result["staleness"]:
        if a["change_id"] == change_id:
            return a
    raise KeyError(f"No annotation found for {change_id}")


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_proposals_returns_empty_staleness():
    result = _detect([])
    assert result["staleness"] == []
    assert result["proposal_count"] == 0
    assert result["stale_count"] == 0
    assert result["aging_count"] == 0
    assert result["summary"] == "No proposals to evaluate."


# ---------------------------------------------------------------------------
# Fresh: no persisted review state
# ---------------------------------------------------------------------------


def test_fresh_no_review_state():
    change = _change()
    result = _detect([change], review_states={})
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "fresh"
    assert ann["severity"] == "low"
    assert any("newly computed" in s for s in ann["signals"])


# ---------------------------------------------------------------------------
# Fresh: recently persisted, pending, category still active
# ---------------------------------------------------------------------------


def test_fresh_recently_created():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=2))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "fresh"


# ---------------------------------------------------------------------------
# Fresh: approved / rejected / archived — terminal states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("terminal_status", ["approved", "rejected", "archived"])
def test_terminal_status_is_fresh(terminal_status):
    change = _change()
    rs = _review_state(
        status=terminal_status,
        created_at=NOW - timedelta(days=30),
    )
    result = _detect([change], review_states={change["change_id"]: rs})
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "fresh"
    assert any(terminal_status in s for s in ann["signals"])


# ---------------------------------------------------------------------------
# Aging: pending > AGING_DAYS
# ---------------------------------------------------------------------------


def test_aging_proposal_at_aging_threshold():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=AGING_DAYS))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "aging"
    assert ann["severity"] == "medium"


def test_aging_proposal_between_thresholds():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=10))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "aging"
    assert any(str(AGING_DAYS) in s for s in ann["signals"])


def test_aging_includes_no_recent_state_change_signal():
    change = _change()
    rs = _review_state(
        created_at=NOW - timedelta(days=10),
        updated_at=NOW - timedelta(days=10),
    )
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "aging"
    assert any("no recent state change" in s for s in ann["signals"])


def test_recently_updated_aging_proposal_omits_no_state_change():
    change = _change()
    rs = _review_state(
        created_at=NOW - timedelta(days=10),
        updated_at=NOW - timedelta(days=1),
    )
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "aging"
    assert not any("no recent state change" in s for s in ann["signals"])


# ---------------------------------------------------------------------------
# Stale: pending too long (>= STALE_DAYS)
# ---------------------------------------------------------------------------


def test_stale_pending_too_long():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=STALE_DAYS))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "stale"
    assert ann["severity"] == "high"
    assert any(str(STALE_DAYS) in s for s in ann["signals"])


def test_stale_well_past_threshold():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=30))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "stale"


# ---------------------------------------------------------------------------
# Stale: supporting control suggestion category disappeared
# ---------------------------------------------------------------------------


def test_stale_because_control_category_disappeared():
    change = _change(category="confidence_threshold_tuning")
    rs = _review_state(created_at=NOW - timedelta(days=3))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=[],  # category no longer active
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "stale"
    assert any("control suggestion category" in s for s in ann["signals"])


def test_stale_category_gone_still_stale_regardless_of_age():
    change = _change(category="confidence_threshold_tuning")
    rs = _review_state(created_at=NOW - timedelta(days=1))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["some_other_category"],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "stale"


# ---------------------------------------------------------------------------
# Stale: both reasons compound
# ---------------------------------------------------------------------------


def test_stale_both_age_and_missing_category():
    change = _change(category="confidence_threshold_tuning")
    rs = _review_state(created_at=NOW - timedelta(days=STALE_DAYS + 5))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=[],
    )
    ann = _annotation_for(result, change["change_id"])
    assert ann["status"] == "stale"
    # Both signals should be present
    signals_text = " ".join(ann["signals"])
    assert str(STALE_DAYS) in signals_text
    assert "control suggestion" in signals_text


# ---------------------------------------------------------------------------
# Superseded: newer proposal on same parameter
# ---------------------------------------------------------------------------


def test_superseded_older_proposal():
    change_old = _change(
        change_id="pipeline:paintly:ct_tuning:review_confidence_threshold",
        parameter="review_confidence_threshold",
    )
    change_new = _change(
        change_id="pipeline:paintly:rt_narrowing:review_confidence_threshold",
        category="review_trigger_narrowing",
        parameter="review_confidence_threshold",
    )
    rs_old = _review_state(created_at=NOW - timedelta(days=5))
    rs_new = _review_state(created_at=NOW - timedelta(days=1))
    result = _detect(
        [change_old, change_new],
        review_states={
            change_old["change_id"]: rs_old,
            change_new["change_id"]: rs_new,
        },
        control_categories=["confidence_threshold_tuning", "review_trigger_narrowing"],
    )
    old_ann = _annotation_for(result, change_old["change_id"])
    new_ann = _annotation_for(result, change_new["change_id"])

    assert old_ann["status"] == "superseded"
    assert old_ann["severity"] == "medium"
    assert new_ann["status"] != "superseded"
    assert any("newer proposal" in s for s in old_ann["signals"])


def test_superseded_only_marks_older_one():
    change_old = _change(
        change_id="pipeline:paintly:ct:rct_old",
        parameter="review_confidence_threshold",
    )
    change_new = _change(
        change_id="pipeline:paintly:ct:rct_new",
        parameter="review_confidence_threshold",
    )
    rs_old = _review_state(created_at=NOW - timedelta(days=10))
    rs_new = _review_state(created_at=NOW - timedelta(days=2))
    result = _detect(
        [change_old, change_new],
        review_states={
            change_old["change_id"]: rs_old,
            change_new["change_id"]: rs_new,
        },
    )
    statuses = {a["change_id"]: a["status"] for a in result["staleness"]}
    assert statuses[change_old["change_id"]] == "superseded"
    assert statuses[change_new["change_id"]] != "superseded"


def test_superseded_requires_both_persisted():
    change_a = _change(change_id="id_a", parameter="review_confidence_threshold")
    change_b = _change(change_id="id_b", parameter="review_confidence_threshold")
    # Only one is persisted — no superseded
    rs_a = _review_state(created_at=NOW - timedelta(days=5))
    result = _detect(
        [change_a, change_b],
        review_states={change_a["change_id"]: rs_a},
    )
    statuses = {a["change_id"]: a["status"] for a in result["staleness"]}
    assert statuses["id_a"] != "superseded"
    assert statuses["id_b"] == "fresh"


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_top_level_output_shape():
    result = _detect([_change()])
    for key in ("scope", "scope_id", "proposal_count", "stale_count", "aging_count", "summary", "staleness"):
        assert key in result, f"Missing top-level key: {key}"
    assert result["scope"] == "pipeline"
    assert result["scope_id"] == "construction"
    assert result["proposal_count"] == 1


def test_annotation_shape():
    change = _change()
    result = _detect([change])
    ann = _annotation_for(result, change["change_id"])
    for key in ("change_id", "status", "severity", "summary", "reason", "signals", "recommendation"):
        assert key in ann, f"Missing annotation key: {key}"
    assert isinstance(ann["signals"], list)
    assert ann["status"] in ("fresh", "aging", "stale", "superseded")
    assert ann["severity"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Summary counters
# ---------------------------------------------------------------------------


def test_stale_count_reflects_stale_annotations():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=20))
    result = _detect([change], review_states={change["change_id"]: rs})
    assert result["stale_count"] == 1
    assert result["stale_count"] == sum(1 for a in result["staleness"] if a["status"] == "stale")


def test_aging_count_reflects_aging_annotations():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=8))
    result = _detect(
        [change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    assert result["aging_count"] == 1


# ---------------------------------------------------------------------------
# Stable output
# ---------------------------------------------------------------------------


def test_stable_output_same_inputs():
    change = _change()
    rs = _review_state(created_at=NOW - timedelta(days=10))
    kwargs = dict(
        changes=[change],
        review_states={change["change_id"]: rs},
        control_categories=["confidence_threshold_tuning"],
    )
    r1 = _detect(**kwargs)
    r2 = _detect(**kwargs)
    assert r1 == r2


# ---------------------------------------------------------------------------
# Scope isolation
# ---------------------------------------------------------------------------


def test_scope_id_in_output():
    change = _change(scope_id="my_pipeline")
    result = _detect([change], scope_id="my_pipeline")
    assert result["scope_id"] == "my_pipeline"


def test_different_scopes_produce_separate_outputs():
    change = _change()
    r_a = _detect([change], scope_id="pipe_a")
    r_b = _detect([change], scope_id="pipe_b")
    assert r_a["scope_id"] == "pipe_a"
    assert r_b["scope_id"] == "pipe_b"


# ---------------------------------------------------------------------------
# Multiple proposals — counts
# ---------------------------------------------------------------------------


def test_multiple_proposals_counted():
    c1 = _change("id1")
    c2 = _change("id2", parameter="fallback_threshold")
    result = _detect([c1, c2])
    assert result["proposal_count"] == 2
    assert len(result["staleness"]) == 2
