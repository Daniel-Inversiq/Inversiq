"""
tests/test_simulation_preview.py

Unit tests for app/services/simulation_preview.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test constructs the minimal input required to exercise a specific
preview category and asserts the expected output shape and content.
"""

from __future__ import annotations

import pytest

from app.services.simulation_preview import compute_simulation_preview


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suggestion(category: str, action: str = "some_action", confidence: str = "medium") -> dict:
    return {"category": category, "action": action, "confidence": confidence}


def _preview(
    suggestions: list | None = None,
    scope_type: str = "pipeline",
    scope_id: str = "test_pipe",
) -> dict:
    return compute_simulation_preview(
        scope_type=scope_type,
        scope_id=scope_id,
        suggestions=suggestions or [],
    )


def _categories(result: dict) -> list[str]:
    return [p["category"] for p in result["previews"]]


def _preview_for(result: dict, category: str) -> dict:
    return next(p for p in result["previews"] if p["category"] == category)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys(self):
        result = _preview()
        assert set(result.keys()) == {"scope", "scope_id", "previews", "summary"}

    def test_scope_and_scope_id_passed_through(self):
        result = _preview(scope_type="vertical", scope_id="my_vertical")
        assert result["scope"] == "vertical"
        assert result["scope_id"] == "my_vertical"

    def test_preview_item_keys(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = result["previews"][0]
        assert set(item.keys()) == {
            "category",
            "action",
            "simulation_summary",
            "expected_impacts",
            "risks",
            "assumptions",
            "safety_checks",
            "confidence",
        }

    def test_expected_impacts_is_list(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = result["previews"][0]
        assert isinstance(item["expected_impacts"], list)

    def test_impact_item_keys(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        impact = result["previews"][0]["expected_impacts"][0]
        assert set(impact.keys()) == {"metric", "direction", "magnitude", "rationale"}

    def test_risks_is_non_empty_list(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert isinstance(result["previews"][0]["risks"], list)
        assert len(result["previews"][0]["risks"]) >= 1

    def test_assumptions_is_non_empty_list(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert isinstance(result["previews"][0]["assumptions"], list)
        assert len(result["previews"][0]["assumptions"]) >= 1

    def test_safety_checks_is_non_empty_list(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert isinstance(result["previews"][0]["safety_checks"], list)
        assert len(result["previews"][0]["safety_checks"]) >= 1

    def test_summary_is_string(self):
        result = _preview()
        assert isinstance(result["summary"], str)

    def test_action_passed_through(self):
        result = _preview([_suggestion("confidence_threshold_tuning", action="lower_review_threshold")])
        assert result["previews"][0]["action"] == "lower_review_threshold"


# ---------------------------------------------------------------------------
# confidence_threshold_tuning
# ---------------------------------------------------------------------------


class TestConfidenceThresholdTuning:
    def test_preview_generated(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert "confidence_threshold_tuning" in _categories(result)

    def test_review_rate_impact_present(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = _preview_for(result, "confidence_threshold_tuning")
        metrics = [i["metric"] for i in item["expected_impacts"]]
        assert "review_rate" in metrics

    def test_review_rate_direction_is_improving(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = _preview_for(result, "confidence_threshold_tuning")
        impact = next(i for i in item["expected_impacts"] if i["metric"] == "review_rate")
        assert impact["direction"] == "improving"

    def test_failed_rate_direction_is_stable(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = _preview_for(result, "confidence_threshold_tuning")
        impact = next((i for i in item["expected_impacts"] if i["metric"] == "failed_rate"), None)
        assert impact is not None
        assert impact["direction"] == "stable"

    def test_safety_checks_mention_failed_rate(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        item = _preview_for(result, "confidence_threshold_tuning")
        joined = " ".join(item["safety_checks"]).lower()
        assert "failed_rate" in joined or "fail" in joined

    def test_confidence_is_medium(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert _preview_for(result, "confidence_threshold_tuning")["confidence"] == "medium"


# ---------------------------------------------------------------------------
# review_trigger_narrowing
# ---------------------------------------------------------------------------


class TestReviewTriggerNarrowing:
    def test_preview_generated(self):
        result = _preview([_suggestion("review_trigger_narrowing")])
        assert "review_trigger_narrowing" in _categories(result)

    def test_review_rate_improving(self):
        result = _preview([_suggestion("review_trigger_narrowing")])
        item = _preview_for(result, "review_trigger_narrowing")
        impact = next(i for i in item["expected_impacts"] if i["metric"] == "review_rate")
        assert impact["direction"] == "improving"

    def test_failed_rate_stable(self):
        result = _preview([_suggestion("review_trigger_narrowing")])
        item = _preview_for(result, "review_trigger_narrowing")
        impact = next((i for i in item["expected_impacts"] if i["metric"] == "failed_rate"), None)
        assert impact is not None
        assert impact["direction"] == "stable"

    def test_confidence_is_medium(self):
        result = _preview([_suggestion("review_trigger_narrowing")])
        assert _preview_for(result, "review_trigger_narrowing")["confidence"] == "medium"


# ---------------------------------------------------------------------------
# validation_step_tightening
# ---------------------------------------------------------------------------


class TestValidationStepTightening:
    def test_preview_generated(self):
        result = _preview([_suggestion("validation_step_tightening")])
        assert "validation_step_tightening" in _categories(result)

    def test_fallback_rate_improving(self):
        result = _preview([_suggestion("validation_step_tightening")])
        item = _preview_for(result, "validation_step_tightening")
        impact = next(i for i in item["expected_impacts"] if i["metric"] == "fallback_rate")
        assert impact["direction"] == "improving"

    def test_risks_mention_throughput_or_rejection(self):
        result = _preview([_suggestion("validation_step_tightening")])
        item = _preview_for(result, "validation_step_tightening")
        joined = " ".join(item["risks"]).lower()
        assert "throughput" in joined or "reject" in joined or "gating" in joined

    def test_safety_checks_mention_run_count_or_throughput(self):
        result = _preview([_suggestion("validation_step_tightening")])
        item = _preview_for(result, "validation_step_tightening")
        joined = " ".join(item["safety_checks"]).lower()
        assert "run_count" in joined or "throughput" in joined

    def test_confidence_is_medium(self):
        result = _preview([_suggestion("validation_step_tightening")])
        assert _preview_for(result, "validation_step_tightening")["confidence"] == "medium"


# ---------------------------------------------------------------------------
# fallback_path_hardening
# ---------------------------------------------------------------------------


class TestFallbackPathHardening:
    def test_preview_generated(self):
        result = _preview([_suggestion("fallback_path_hardening")])
        assert "fallback_path_hardening" in _categories(result)

    def test_fallback_rate_improving(self):
        result = _preview([_suggestion("fallback_path_hardening")])
        item = _preview_for(result, "fallback_path_hardening")
        impact = next(i for i in item["expected_impacts"] if i["metric"] == "fallback_rate")
        assert impact["direction"] == "improving"

    def test_risks_present(self):
        result = _preview([_suggestion("fallback_path_hardening")])
        assert len(_preview_for(result, "fallback_path_hardening")["risks"]) >= 1

    def test_safety_checks_mention_failed_rate(self):
        result = _preview([_suggestion("fallback_path_hardening")])
        item = _preview_for(result, "fallback_path_hardening")
        joined = " ".join(item["safety_checks"]).lower()
        assert "failed_rate" in joined or "fail" in joined

    def test_confidence_is_medium(self):
        result = _preview([_suggestion("fallback_path_hardening")])
        assert _preview_for(result, "fallback_path_hardening")["confidence"] == "medium"


# ---------------------------------------------------------------------------
# margin_guardrail_adjustment
# ---------------------------------------------------------------------------


class TestMarginGuardrailAdjustment:
    def test_preview_generated(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        assert "margin_guardrail_adjustment" in _categories(result)

    def test_underpricing_rate_improving(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        item = _preview_for(result, "margin_guardrail_adjustment")
        impact = next(i for i in item["expected_impacts"] if i["metric"] == "underpricing_rate")
        assert impact["direction"] == "improving"

    def test_win_rate_stable(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        item = _preview_for(result, "margin_guardrail_adjustment")
        impact = next((i for i in item["expected_impacts"] if i["metric"] == "win_rate"), None)
        assert impact is not None
        assert impact["direction"] == "stable"

    def test_risks_mention_win_rate(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        item = _preview_for(result, "margin_guardrail_adjustment")
        joined = " ".join(item["risks"]).lower()
        assert "win rate" in joined or "win_rate" in joined

    def test_safety_checks_mention_win_rate_or_underpricing(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        item = _preview_for(result, "margin_guardrail_adjustment")
        joined = " ".join(item["safety_checks"]).lower()
        assert "win_rate" in joined or "underpricing" in joined

    def test_confidence_is_medium(self):
        result = _preview([_suggestion("margin_guardrail_adjustment")])
        assert _preview_for(result, "margin_guardrail_adjustment")["confidence"] == "medium"


# ---------------------------------------------------------------------------
# no_safe_adjustment fallback
# ---------------------------------------------------------------------------


class TestNoSafeAdjustment:
    def test_no_safe_adjustment_preview_generated(self):
        result = _preview([_suggestion("no_safe_adjustment", action="no_action", confidence="low")])
        assert "no_safe_adjustment" in _categories(result)

    def test_no_safe_adjustment_expected_impacts_empty(self):
        result = _preview([_suggestion("no_safe_adjustment", confidence="low")])
        item = _preview_for(result, "no_safe_adjustment")
        assert item["expected_impacts"] == []

    def test_no_safe_adjustment_confidence_is_low(self):
        result = _preview([_suggestion("no_safe_adjustment", confidence="low")])
        assert _preview_for(result, "no_safe_adjustment")["confidence"] == "low"

    def test_empty_suggestions_produces_empty_previews(self):
        result = _preview([])
        assert result["previews"] == []

    def test_summary_no_previews(self):
        result = _preview([])
        assert "no" in result["summary"].lower() or "0" in result["summary"]


# ---------------------------------------------------------------------------
# Deduplicated safety checks
# ---------------------------------------------------------------------------


class TestDeduplicatedSafetyChecks:
    def test_duplicate_safety_checks_removed(self):
        from app.services.simulation_preview import _deduplicate_safety_checks

        previews = [
            {
                "safety_checks": [
                    "Re-check failed_rate before applying.",
                    "Re-check failed_rate before applying.",
                    "Monitor review_rate after one full comparison window.",
                ]
            }
        ]
        result = _deduplicate_safety_checks(previews)
        assert result[0]["safety_checks"] == [
            "Re-check failed_rate before applying.",
            "Monitor review_rate after one full comparison window.",
        ]

    def test_unique_safety_checks_preserved(self):
        from app.services.simulation_preview import _deduplicate_safety_checks

        checks = ["Check A.", "Check B.", "Check C."]
        previews = [{"safety_checks": checks}]
        result = _deduplicate_safety_checks(previews)
        assert result[0]["safety_checks"] == checks


# ---------------------------------------------------------------------------
# Ordering and summary
# ---------------------------------------------------------------------------


class TestOrderingAndSummary:
    def test_medium_confidence_before_low(self):
        result = _preview([
            _suggestion("no_safe_adjustment", confidence="low"),
            _suggestion("confidence_threshold_tuning", confidence="medium"),
        ])
        confs = [p["confidence"] for p in result["previews"]]
        weights = {"medium": 2, "low": 1}
        scores = [weights[c] for c in confs]
        assert scores == sorted(scores, reverse=True)

    def test_summary_single_preview(self):
        result = _preview([_suggestion("confidence_threshold_tuning")])
        assert "one" in result["summary"].lower() or "1" in result["summary"]
        assert "confidence_threshold_tuning" in result["summary"]

    def test_summary_multiple_previews(self):
        result = _preview([
            _suggestion("confidence_threshold_tuning"),
            _suggestion("margin_guardrail_adjustment"),
        ])
        assert "2" in result["summary"] or "two" in result["summary"].lower()

    def test_all_categories_unique(self):
        result = _preview([
            _suggestion("confidence_threshold_tuning"),
            _suggestion("review_trigger_narrowing"),
            _suggestion("validation_step_tightening"),
            _suggestion("fallback_path_hardening"),
            _suggestion("margin_guardrail_adjustment"),
        ])
        cats = _categories(result)
        assert len(cats) == len(set(cats))
