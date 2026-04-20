"""
tests/test_control_suggestions.py

Unit tests for app/services/control_suggestions.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test constructs the minimal signal combination required to trigger
a specific suggestion category and asserts the expected output shape.
"""

from __future__ import annotations

import pytest

from app.services.control_suggestions import compute_control_suggestions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(name: str, direction: str, severity: str | None = None) -> dict:
    return {"name": name, "direction": direction, "severity": severity}


def _suggest(
    scope_type: str = "pipeline",
    scope_id: str = "test_pipe",
    health_status: str = "watch",
    metric_trends: list | None = None,
    signal_counts: dict | None = None,
    reasoning_categories: list | None = None,
) -> dict:
    return compute_control_suggestions(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health_status,
        metric_trends=metric_trends or [],
        signal_counts=signal_counts or {},
        reasoning_categories=reasoning_categories or [],
    )


def _categories(result: dict) -> list[str]:
    return [s["category"] for s in result["suggestions"]]


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys(self):
        result = _suggest()
        assert set(result.keys()) == {"scope", "scope_id", "suggestions", "summary"}

    def test_suggestion_item_keys(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("failed_rate", "stable")],
        )
        item = result["suggestions"][0]
        assert set(item.keys()) == {
            "category",
            "action",
            "reason",
            "proposed_change",
            "expected_effect",
            "guardrails",
            "confidence",
        }

    def test_suggestion_item_reason_is_string(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        assert isinstance(result["suggestions"][0]["reason"], str)
        assert len(result["suggestions"][0]["reason"]) > 0

    def test_suggestion_item_expected_effect_is_list(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        assert isinstance(result["suggestions"][0]["expected_effect"], list)
        assert len(result["suggestions"][0]["expected_effect"]) >= 1

    def test_suggestion_item_guardrails_is_list(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        assert isinstance(result["suggestions"][0]["guardrails"], list)
        assert len(result["suggestions"][0]["guardrails"]) >= 1

    def test_summary_is_string(self):
        result = _suggest()
        assert isinstance(result["summary"], str)

    def test_scope_and_scope_id_passed_through(self):
        result = _suggest(scope_type="vertical", scope_id="my_vertical")
        assert result["scope"] == "vertical"
        assert result["scope_id"] == "my_vertical"


# ---------------------------------------------------------------------------
# confidence_threshold_tuning
# ---------------------------------------------------------------------------


class TestConfidenceThresholdTuning:
    def test_triggers_on_mismatch_with_stable_failed_rate(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("failed_rate", "stable")],
        )
        assert "confidence_threshold_tuning" in _categories(result)

    def test_triggers_when_failed_rate_absent(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        assert "confidence_threshold_tuning" in _categories(result)

    def test_triggers_on_low_severity_failed_rate(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("failed_rate", "degrading", "low")],
        )
        assert "confidence_threshold_tuning" in _categories(result)

    def test_suppressed_when_failed_rate_medium_degrading(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("failed_rate", "degrading", "medium")],
        )
        assert "confidence_threshold_tuning" not in _categories(result)

    def test_suppressed_when_failed_rate_high_degrading(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("failed_rate", "degrading", "high")],
        )
        assert "confidence_threshold_tuning" not in _categories(result)

    def test_proposed_change_is_decrease(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        item = next(s for s in result["suggestions"] if s["category"] == "confidence_threshold_tuning")
        assert item["proposed_change"]["direction"] == "decrease"
        assert item["proposed_change"]["suggested_delta"] > 0

    def test_bounded_range_present(self):
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        item = next(s for s in result["suggestions"] if s["category"] == "confidence_threshold_tuning")
        br = item["proposed_change"]["bounded_range"]
        assert "min" in br and "max" in br
        assert br["min"] < br["max"]

    def test_not_triggered_without_category(self):
        result = _suggest(reasoning_categories=["operator_backlog"])
        assert "confidence_threshold_tuning" not in _categories(result)


# ---------------------------------------------------------------------------
# review_trigger_narrowing
# ---------------------------------------------------------------------------


class TestReviewTriggerNarrowing:
    def test_triggers_on_operator_backlog_stable_failures(self):
        result = _suggest(
            reasoning_categories=["operator_backlog"],
            metric_trends=[_metric("failed_rate", "stable")],
        )
        assert "review_trigger_narrowing" in _categories(result)

    def test_triggers_on_operator_backlog_no_failed_rate(self):
        result = _suggest(reasoning_categories=["operator_backlog"])
        assert "review_trigger_narrowing" in _categories(result)

    def test_triggers_on_anomaly_sensitivity_with_degrading_review_rate(self):
        result = _suggest(
            reasoning_categories=["anomaly_sensitivity_shift"],
            metric_trends=[
                _metric("review_rate", "degrading", "medium"),
                _metric("failed_rate", "stable"),
            ],
        )
        assert "review_trigger_narrowing" in _categories(result)

    def test_triggers_on_rule_coverage_gap_with_degrading_review_rate(self):
        result = _suggest(
            reasoning_categories=["rule_coverage_gap"],
            metric_trends=[
                _metric("review_rate", "degrading", "low"),
                _metric("failed_rate", "stable"),
            ],
        )
        assert "review_trigger_narrowing" in _categories(result)

    def test_suppressed_on_rule_coverage_gap_without_degrading_review_rate(self):
        result = _suggest(
            reasoning_categories=["rule_coverage_gap"],
            metric_trends=[_metric("review_rate", "stable")],
        )
        assert "review_trigger_narrowing" not in _categories(result)

    def test_proposed_change_is_decrease(self):
        result = _suggest(reasoning_categories=["operator_backlog"])
        item = next(s for s in result["suggestions"] if s["category"] == "review_trigger_narrowing")
        assert item["proposed_change"]["direction"] == "decrease"

    def test_guardrails_present(self):
        result = _suggest(reasoning_categories=["operator_backlog"])
        item = next(s for s in result["suggestions"] if s["category"] == "review_trigger_narrowing")
        assert len(item["guardrails"]) >= 1


# ---------------------------------------------------------------------------
# validation_step_tightening
# ---------------------------------------------------------------------------


class TestValidationStepTightening:
    def test_triggers_on_upstream_quality_with_degrading_fallback(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
        )
        assert "validation_step_tightening" in _categories(result)

    def test_not_triggered_without_degrading_fallback(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "stable")],
        )
        assert "validation_step_tightening" not in _categories(result)

    def test_not_triggered_without_upstream_category(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
        )
        assert "validation_step_tightening" not in _categories(result)

    def test_proposed_change_is_increase(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
        )
        item = next(s for s in result["suggestions"] if s["category"] == "validation_step_tightening")
        assert item["proposed_change"]["direction"] == "increase"

    def test_guardrails_mention_failure_rate(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
        )
        item = next(s for s in result["suggestions"] if s["category"] == "validation_step_tightening")
        all_guardrails = " ".join(item["guardrails"]).lower()
        assert "failure" in all_guardrails or "fail" in all_guardrails


# ---------------------------------------------------------------------------
# fallback_path_hardening
# ---------------------------------------------------------------------------


class TestFallbackPathHardening:
    def test_triggers_on_upstream_quality_with_repeated_fallback_signal(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            signal_counts={"repeated_fallback": 3},
        )
        assert "fallback_path_hardening" in _categories(result)

    def test_not_triggered_without_repeated_fallback_signal(self):
        result = _suggest(reasoning_categories=["upstream_input_quality"])
        assert "fallback_path_hardening" not in _categories(result)

    def test_not_triggered_without_upstream_category(self):
        result = _suggest(signal_counts={"repeated_fallback": 3})
        assert "fallback_path_hardening" not in _categories(result)

    def test_proposed_change_is_increase(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            signal_counts={"repeated_fallback": 2},
        )
        item = next(s for s in result["suggestions"] if s["category"] == "fallback_path_hardening")
        assert item["proposed_change"]["direction"] == "increase"

    def test_delta_larger_than_tightening(self):
        result_hard = _suggest(
            reasoning_categories=["upstream_input_quality"],
            signal_counts={"repeated_fallback": 2},
        )
        result_tight = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
        )
        hard_item = next(s for s in result_hard["suggestions"] if s["category"] == "fallback_path_hardening")
        tight_item = next(s for s in result_tight["suggestions"] if s["category"] == "validation_step_tightening")
        assert hard_item["proposed_change"]["suggested_delta"] >= tight_item["proposed_change"]["suggested_delta"]


# ---------------------------------------------------------------------------
# margin_guardrail_adjustment
# ---------------------------------------------------------------------------


class TestMarginGuardrailAdjustment:
    def test_triggers_on_pricing_calibration_issue(self):
        result = _suggest(reasoning_categories=["pricing_calibration_issue"])
        assert "margin_guardrail_adjustment" in _categories(result)

    def test_not_triggered_without_pricing_category(self):
        result = _suggest(reasoning_categories=["operator_backlog"])
        assert "margin_guardrail_adjustment" not in _categories(result)

    def test_proposed_change_is_increase(self):
        result = _suggest(reasoning_categories=["pricing_calibration_issue"])
        item = next(s for s in result["suggestions"] if s["category"] == "margin_guardrail_adjustment")
        assert item["proposed_change"]["direction"] == "increase"

    def test_bounded_range_present_and_valid(self):
        result = _suggest(reasoning_categories=["pricing_calibration_issue"])
        item = next(s for s in result["suggestions"] if s["category"] == "margin_guardrail_adjustment")
        br = item["proposed_change"]["bounded_range"]
        assert br["min"] > 0
        assert br["max"] > br["min"]

    def test_guardrails_mention_win_rate_or_pricing(self):
        result = _suggest(reasoning_categories=["pricing_calibration_issue"])
        item = next(s for s in result["suggestions"] if s["category"] == "margin_guardrail_adjustment")
        all_guardrails = " ".join(item["guardrails"]).lower()
        assert "win rate" in all_guardrails or "pricing" in all_guardrails or "margin" in all_guardrails


# ---------------------------------------------------------------------------
# no_safe_adjustment fallback
# ---------------------------------------------------------------------------


class TestNoSafeAdjustment:
    def test_returns_no_safe_adjustment_when_no_rules_match(self):
        result = _suggest(reasoning_categories=[], metric_trends=[], signal_counts={})
        assert _categories(result) == ["no_safe_adjustment"]

    def test_no_safe_adjustment_has_none_proposed_change(self):
        result = _suggest()
        item = result["suggestions"][0]
        assert item["proposed_change"] is None

    def test_summary_says_no_suggestion(self):
        result = _suggest()
        assert "no" in result["summary"].lower() or "none" in result["summary"].lower()

    def test_no_safe_adjustment_confidence_is_low(self):
        result = _suggest()
        assert result["suggestions"][0]["confidence"] == "low"

    def test_no_safe_adjustment_health_status_in_reason(self):
        result = _suggest(health_status="unhealthy")
        reason = result["suggestions"][0]["reason"]
        assert "unhealthy" in reason


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_operator_backlog_and_anomaly_shift_both_want_review_narrowing(self):
        result = _suggest(
            reasoning_categories=["operator_backlog", "anomaly_sensitivity_shift"],
            metric_trends=[
                _metric("review_rate", "degrading", "medium"),
                _metric("failed_rate", "stable"),
            ],
        )
        narrowing_count = sum(1 for s in result["suggestions"] if s["category"] == "review_trigger_narrowing")
        assert narrowing_count == 1

    def test_upstream_quality_with_both_fallback_triggers(self):
        result = _suggest(
            reasoning_categories=["upstream_input_quality"],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
            signal_counts={"repeated_fallback": 2},
        )
        cats = _categories(result)
        assert cats.count("validation_step_tightening") == 1
        assert cats.count("fallback_path_hardening") == 1

    def test_all_categories_unique(self):
        result = _suggest(
            reasoning_categories=[
                "confidence_threshold_mismatch",
                "operator_backlog",
                "upstream_input_quality",
                "pricing_calibration_issue",
            ],
            metric_trends=[_metric("fallback_rate", "degrading", "medium")],
            signal_counts={"repeated_fallback": 2},
        )
        cats = _categories(result)
        assert len(cats) == len(set(cats))


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_no_safe_adjustment_appears_last_when_mixed(self):
        # no_safe_adjustment only appears when there are no other suggestions,
        # so verify that when suggestions exist, no_safe_adjustment is absent
        result = _suggest(reasoning_categories=["confidence_threshold_mismatch"])
        assert "no_safe_adjustment" not in _categories(result)

    def test_suggestions_sorted_by_confidence_weight_descending(self):
        result = _suggest(
            reasoning_categories=[
                "confidence_threshold_mismatch",
                "pricing_calibration_issue",
            ],
        )
        weights = {"high": 3, "medium": 2, "low": 1}
        scores = [weights.get(s["confidence"], 0) for s in result["suggestions"]]
        assert scores == sorted(scores, reverse=True)

    def test_summary_mentions_count_when_multiple(self):
        result = _suggest(
            reasoning_categories=["confidence_threshold_mismatch", "pricing_calibration_issue"],
        )
        assert "2" in result["summary"] or "two" in result["summary"].lower()

    def test_summary_mentions_category_when_single(self):
        result = _suggest(reasoning_categories=["pricing_calibration_issue"])
        assert "margin_guardrail_adjustment" in result["summary"]
