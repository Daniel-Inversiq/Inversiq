"""
tests/test_proposed_changes.py

Unit tests for app/services/proposed_changes.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test constructs the minimal input combination required to produce
a specific proposed change category and asserts the expected output shape.
"""

from __future__ import annotations

import pytest

from app.services.proposed_changes import compute_proposed_changes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(name: str, direction: str, severity: str | None = None) -> dict:
    return {"name": name, "direction": direction, "severity": severity}


def _propose(
    scope_type: str = "pipeline",
    scope_id: str = "test_pipe",
    suggestions: list | None = None,
    reasoning_categories: list | None = None,
    metric_trends: list | None = None,
    signal_counts: dict | None = None,
) -> dict:
    return compute_proposed_changes(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=suggestions or [],
        reasoning_categories=reasoning_categories or [],
        metric_trends=metric_trends or [],
        signal_counts=signal_counts or {},
    )


def _suggestion(
    category: str,
    parameter: str = "some_parameter",
    direction: str = "decrease",
    delta: float = 0.05,
    bounded_range: dict | None = None,
    action: str = "some_action",
    reason: str = "Test reason.",
    expected_effect: list | None = None,
) -> dict:
    return {
        "category": category,
        "action": action,
        "reason": reason,
        "proposed_change": {
            "parameter": parameter,
            "direction": direction,
            "suggested_delta": delta,
            "bounded_range": bounded_range or {"min": 0.50, "max": 0.90},
        },
        "expected_effect": expected_effect or ["Some expected effect."],
        "guardrails": ["Some guardrail."],
        "confidence": "medium",
    }


def _no_safe_suggestion() -> dict:
    return {
        "category": "no_safe_adjustment",
        "action": "no_action",
        "reason": "No bounded suggestion.",
        "proposed_change": None,
        "expected_effect": ["No change proposed."],
        "guardrails": ["Continue monitoring."],
        "confidence": "low",
    }


def _change_types(result: dict) -> list[str]:
    return [c["change_type"] for c in result["proposed_changes"]]


def _categories(result: dict) -> list[str]:
    return [c["category"] for c in result["proposed_changes"]]


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys(self):
        result = _propose()
        assert set(result.keys()) == {"scope", "scope_id", "proposed_changes", "summary"}

    def test_scope_and_scope_id_passed_through(self):
        result = _propose(scope_type="vertical", scope_id="my_vertical")
        assert result["scope"] == "vertical"
        assert result["scope_id"] == "my_vertical"

    def test_summary_is_string(self):
        result = _propose()
        assert isinstance(result["summary"], str)

    def test_proposed_changes_is_list(self):
        result = _propose()
        assert isinstance(result["proposed_changes"], list)

    def test_change_item_keys(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = result["proposed_changes"][0]
        expected_keys = {
            "change_id",
            "category",
            "title",
            "change_type",
            "target",
            "proposed_change",
            "reason",
            "expected_effect",
            "preconditions",
            "approval_intent",
            "rollback_hint",
            "evidence",
            "status",
        }
        assert set(item.keys()) == expected_keys

    def test_status_is_proposal_only(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        for item in result["proposed_changes"]:
            assert item["status"] == "proposal_only"

    def test_target_block_shape(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
            scope_type="pipeline",
            scope_id="construction",
        )
        target = result["proposed_changes"][0]["target"]
        assert target["scope_type"] == "pipeline"
        assert target["scope_id"] == "construction"
        assert target["parameter"] == "review_confidence_threshold"

    def test_approval_intent_block_shape(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        ai = result["proposed_changes"][0]["approval_intent"]
        assert "requires_human_review" in ai
        assert "risk_level" in ai
        assert "approval_type" in ai
        assert ai["requires_human_review"] is True

    def test_preconditions_is_list(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        assert isinstance(result["proposed_changes"][0]["preconditions"], list)

    def test_rollback_hint_is_list(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        assert isinstance(result["proposed_changes"][0]["rollback_hint"], list)

    def test_evidence_is_list(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        assert isinstance(result["proposed_changes"][0]["evidence"], list)
        assert len(result["proposed_changes"][0]["evidence"]) >= 1


# ---------------------------------------------------------------------------
# threshold_adjustment (confidence_threshold_tuning)
# ---------------------------------------------------------------------------


class TestThresholdAdjustment:
    def test_maps_to_threshold_adjustment(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        assert "threshold_adjustment" in _change_types(result)

    def test_risk_level_is_medium(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "threshold_adjustment")
        assert item["approval_intent"]["risk_level"] == "medium"

    def test_approval_type_is_operator_confirmation(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "threshold_adjustment")
        assert item["approval_intent"]["approval_type"] == "operator_confirmation"

    def test_preconditions_not_empty(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "threshold_adjustment")
        assert len(item["preconditions"]) >= 1

    def test_rollback_hint_not_empty(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "threshold_adjustment")
        assert len(item["rollback_hint"]) >= 1

    def test_proposed_change_block_preserved(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold", direction="decrease", delta=0.05)],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "threshold_adjustment")
        pc = item["proposed_change"]
        assert pc["direction"] == "decrease"
        assert pc["suggested_delta"] == 0.05
        assert "bounded_range" in pc


# ---------------------------------------------------------------------------
# review_trigger_adjustment (review_trigger_narrowing)
# ---------------------------------------------------------------------------


class TestReviewTriggerAdjustment:
    def test_maps_to_review_trigger_adjustment(self):
        result = _propose(
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        assert "review_trigger_adjustment" in _change_types(result)

    def test_risk_level_is_medium(self):
        result = _propose(
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "review_trigger_adjustment")
        assert item["approval_intent"]["risk_level"] == "medium"

    def test_preconditions_present(self):
        result = _propose(
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "review_trigger_adjustment")
        assert len(item["preconditions"]) >= 1

    def test_rollback_hint_present(self):
        result = _propose(
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "review_trigger_adjustment")
        assert len(item["rollback_hint"]) >= 1


# ---------------------------------------------------------------------------
# validation_policy_adjustment (validation_step_tightening)
# ---------------------------------------------------------------------------


class TestValidationPolicyAdjustment:
    def test_maps_to_validation_policy_adjustment(self):
        result = _propose(
            suggestions=[_suggestion("validation_step_tightening", parameter="fallback_validation_strictness")],
        )
        assert "validation_policy_adjustment" in _change_types(result)

    def test_risk_level_is_medium(self):
        result = _propose(
            suggestions=[_suggestion("validation_step_tightening", parameter="fallback_validation_strictness")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "validation_policy_adjustment")
        assert item["approval_intent"]["risk_level"] == "medium"

    def test_preconditions_present(self):
        result = _propose(
            suggestions=[_suggestion("validation_step_tightening", parameter="fallback_validation_strictness")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "validation_policy_adjustment")
        assert len(item["preconditions"]) >= 1


# ---------------------------------------------------------------------------
# fallback_policy_adjustment (fallback_path_hardening)
# ---------------------------------------------------------------------------


class TestFallbackPolicyAdjustment:
    def test_maps_to_fallback_policy_adjustment(self):
        result = _propose(
            suggestions=[_suggestion("fallback_path_hardening", parameter="fallback_validation_strictness")],
        )
        assert "fallback_policy_adjustment" in _change_types(result)

    def test_risk_level_is_medium(self):
        result = _propose(
            suggestions=[_suggestion("fallback_path_hardening", parameter="fallback_validation_strictness")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "fallback_policy_adjustment")
        assert item["approval_intent"]["risk_level"] == "medium"

    def test_rollback_hint_present(self):
        result = _propose(
            suggestions=[_suggestion("fallback_path_hardening", parameter="fallback_validation_strictness")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "fallback_policy_adjustment")
        assert len(item["rollback_hint"]) >= 1


# ---------------------------------------------------------------------------
# pricing_guardrail_adjustment (margin_guardrail_adjustment)
# ---------------------------------------------------------------------------


class TestPricingGuardrailAdjustment:
    def test_maps_to_pricing_guardrail_adjustment(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        assert "pricing_guardrail_adjustment" in _change_types(result)

    def test_risk_level_is_high(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "pricing_guardrail_adjustment")
        assert item["approval_intent"]["risk_level"] == "high"

    def test_approval_type_is_senior_review(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "pricing_guardrail_adjustment")
        assert item["approval_intent"]["approval_type"] == "senior_review"

    def test_preconditions_mention_win_rate_or_pricing(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "pricing_guardrail_adjustment")
        all_preconditions = " ".join(item["preconditions"]).lower()
        assert "win_rate" in all_preconditions or "pricing" in all_preconditions or "margin" in all_preconditions

    def test_rollback_hint_mentions_win_rate_or_pricing(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        item = next(c for c in result["proposed_changes"] if c["change_type"] == "pricing_guardrail_adjustment")
        all_hints = " ".join(item["rollback_hint"]).lower()
        assert "win_rate" in all_hints or "pricing" in all_hints or "margin" in all_hints


# ---------------------------------------------------------------------------
# no_action_proposed (no_safe_adjustment)
# ---------------------------------------------------------------------------


class TestNoActionProposed:
    def test_maps_to_no_action_proposed(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        assert "no_action_proposed" in _change_types(result)

    def test_risk_level_is_low(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        item = result["proposed_changes"][0]
        assert item["approval_intent"]["risk_level"] == "low"

    def test_proposed_change_block_is_none(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        item = result["proposed_changes"][0]
        assert item["proposed_change"] is None

    def test_preconditions_empty(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        item = result["proposed_changes"][0]
        assert item["preconditions"] == []

    def test_rollback_hint_empty(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        item = result["proposed_changes"][0]
        assert item["rollback_hint"] == []

    def test_summary_says_generated(self):
        result = _propose(suggestions=[_no_safe_suggestion()])
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_empty_suggestions_returns_empty_list(self):
        result = _propose(suggestions=[])
        assert result["proposed_changes"] == []
        assert "no" in result["summary"].lower() or "0" in result["summary"].lower()


# ---------------------------------------------------------------------------
# Stable change_id generation
# ---------------------------------------------------------------------------


class TestChangeIdGeneration:
    def test_change_id_format(self):
        result = _propose(
            scope_type="pipeline",
            scope_id="construction",
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
        )
        item = result["proposed_changes"][0]
        assert item["change_id"] == "pipeline:paintly:confidence_threshold_tuning:review_confidence_threshold"

    def test_change_id_stable_across_calls(self):
        kwargs = dict(
            scope_type="pipeline",
            scope_id="construction",
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        r1 = _propose(**kwargs)
        r2 = _propose(**kwargs)
        assert r1["proposed_changes"][0]["change_id"] == r2["proposed_changes"][0]["change_id"]

    def test_change_id_includes_scope_and_category(self):
        result = _propose(
            scope_type="vertical",
            scope_id="construction",
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        cid = result["proposed_changes"][0]["change_id"]
        assert "vertical" in cid
        assert "construction" in cid
        assert "review_trigger_narrowing" in cid


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_change_ids_deduplicated(self):
        s = _suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")
        result = _propose(
            scope_type="pipeline",
            scope_id="construction",
            suggestions=[s, s],
        )
        cids = [c["change_id"] for c in result["proposed_changes"]]
        assert len(cids) == len(set(cids))

    def test_different_categories_not_deduplicated(self):
        result = _propose(
            suggestions=[
                _suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold"),
                _suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor"),
            ],
        )
        assert len(result["proposed_changes"]) == 2


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_pricing_guardrail_ranked_above_threshold(self):
        result = _propose(
            suggestions=[
                _suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold"),
                _suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor"),
            ],
        )
        types = _change_types(result)
        assert types.index("pricing_guardrail_adjustment") < types.index("threshold_adjustment")

    def test_no_action_proposed_ranked_last(self):
        result = _propose(
            suggestions=[
                _suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold"),
                _no_safe_suggestion(),
            ],
        )
        types = _change_types(result)
        assert types[-1] == "no_action_proposed"

    def test_summary_mentions_count_for_multiple(self):
        result = _propose(
            suggestions=[
                _suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold"),
                _suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor"),
            ],
        )
        assert "2" in result["summary"] or "two" in result["summary"].lower()

    def test_summary_mentions_category_for_single(self):
        result = _propose(
            suggestions=[_suggestion("margin_guardrail_adjustment", parameter="margin_protection_floor")],
        )
        assert "margin_guardrail_adjustment" in result["summary"]


# ---------------------------------------------------------------------------
# Evidence generation
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_evidence_captures_review_rate_trend(self):
        result = _propose(
            suggestions=[_suggestion("confidence_threshold_tuning", parameter="review_confidence_threshold")],
            metric_trends=[_metric("review_rate", "degrading", "medium")],
            reasoning_categories=["confidence_threshold_mismatch"],
        )
        item = next(c for c in result["proposed_changes"] if c["category"] == "confidence_threshold_tuning")
        all_evidence = " ".join(item["evidence"]).lower()
        assert "review_rate" in all_evidence or "review" in all_evidence

    def test_evidence_captures_repeated_fallback_signal(self):
        result = _propose(
            suggestions=[_suggestion("fallback_path_hardening", parameter="fallback_validation_strictness")],
            signal_counts={"repeated_fallback": 5},
        )
        item = next(c for c in result["proposed_changes"] if c["category"] == "fallback_path_hardening")
        all_evidence = " ".join(item["evidence"])
        assert "5" in all_evidence or "repeated_fallback" in all_evidence.lower()

    def test_evidence_not_empty_when_no_specific_signals(self):
        result = _propose(
            suggestions=[_suggestion("review_trigger_narrowing", parameter="review_trigger_sensitivity")],
        )
        item = result["proposed_changes"][0]
        assert len(item["evidence"]) >= 1
