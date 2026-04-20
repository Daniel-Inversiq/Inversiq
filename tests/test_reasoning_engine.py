"""
tests/test_reasoning_engine.py

Unit tests for app/services/reasoning_engine.py.

All tests operate on plain dicts — no DB, no HTTP.
Each test constructs the minimal signal combination required to trigger
a specific reasoning category and asserts the expected output shape.
"""

from __future__ import annotations

import pytest

from app.services.reasoning_engine import run_reasoning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(name: str, direction: str, severity: str | None = None) -> dict:
    return {"name": name, "direction": direction, "severity": severity}


def _reason(
    scope_type: str = "pipeline",
    scope_id: str = "test_pipe",
    health_status: str = "watch",
    metric_trends: list | None = None,
    signal_counts: dict | None = None,
) -> dict:
    return run_reasoning(
        scope_type=scope_type,
        scope_id=scope_id,
        health_status=health_status,
        metric_trends=metric_trends or [],
        signal_counts=signal_counts or {},
    )


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_top_level_keys(self):
        result = _reason()
        assert set(result.keys()) == {"scope", "scope_id", "health_status", "reasoning", "summary"}

    def test_reasoning_item_keys(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "medium"),
            ]
        )
        item = result["reasoning"][0]
        assert set(item.keys()) == {"category", "root_cause", "confidence", "evidence", "recommendations"}

    def test_reasoning_items_are_list(self):
        result = _reason()
        assert isinstance(result["reasoning"], list)
        assert len(result["reasoning"]) >= 1

    def test_summary_is_string(self):
        result = _reason()
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# upstream_input_quality
# ---------------------------------------------------------------------------


class TestUpstreamInputQuality:
    def test_failed_plus_fallback(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "medium"),
            ]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "upstream_input_quality" in categories

    def test_failed_plus_confidence(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "degrading", "medium"),
                _metric("avg_confidence", "degrading", "medium"),
            ]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "upstream_input_quality" in categories

    def test_failed_plus_repeated_fallback_signal(self):
        result = _reason(
            metric_trends=[_metric("failed_rate", "degrading", "low")],
            signal_counts={"REPEATED_FALLBACK": 3},
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "upstream_input_quality" in categories

    def test_failed_alone_does_not_trigger(self):
        result = _reason(metric_trends=[_metric("failed_rate", "degrading", "medium")])
        categories = [r["category"] for r in result["reasoning"]]
        assert "upstream_input_quality" not in categories

    def test_high_severity_yields_high_confidence(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "high"),
            ]
        )
        item = next(r for r in result["reasoning"] if r["category"] == "upstream_input_quality")
        assert item["confidence"] == "high"

    def test_evidence_mentions_failed_rate(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "medium"),
            ]
        )
        item = next(r for r in result["reasoning"] if r["category"] == "upstream_input_quality")
        assert any("failed_rate" in e for e in item["evidence"])


# ---------------------------------------------------------------------------
# confidence_threshold_mismatch
# ---------------------------------------------------------------------------


class TestConfidenceThresholdMismatch:
    def test_review_rate_plus_avg_confidence(self):
        result = _reason(
            metric_trends=[
                _metric("review_rate", "degrading", "medium"),
                _metric("avg_confidence", "degrading", "medium"),
            ]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "confidence_threshold_mismatch" in categories

    def test_review_rate_plus_low_confidence_rate(self):
        result = _reason(
            metric_trends=[
                _metric("review_rate", "degrading", "medium"),
                _metric("low_confidence_rate", "degrading", "medium"),
            ]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "confidence_threshold_mismatch" in categories

    def test_review_rate_plus_repeated_low_conf_signal(self):
        result = _reason(
            metric_trends=[_metric("review_rate", "degrading", "medium")],
            signal_counts={"REPEATED_LOW_CONFIDENCE": 4},
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "confidence_threshold_mismatch" in categories

    def test_review_rate_alone_does_not_trigger(self):
        result = _reason(metric_trends=[_metric("review_rate", "degrading", "medium")])
        categories = [r["category"] for r in result["reasoning"]]
        assert "confidence_threshold_mismatch" not in categories


# ---------------------------------------------------------------------------
# pricing_calibration_issue
# ---------------------------------------------------------------------------


class TestPricingCalibrationIssue:
    def test_underpricing_metric_degrading(self):
        result = _reason(
            metric_trends=[_metric("underpricing_rate", "degrading", "medium")]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "pricing_calibration_issue" in categories

    def test_likely_underpricing_signal(self):
        result = _reason(signal_counts={"LIKELY_UNDERPRICING": 2})
        categories = [r["category"] for r in result["reasoning"]]
        assert "pricing_calibration_issue" in categories

    def test_likely_overpricing_signal(self):
        result = _reason(signal_counts={"LIKELY_OVERPRICING": 1})
        categories = [r["category"] for r in result["reasoning"]]
        assert "pricing_calibration_issue" in categories

    def test_no_pricing_signals_does_not_trigger(self):
        result = _reason(
            metric_trends=[
                _metric("failed_rate", "stable", None),
                _metric("avg_confidence", "stable", None),
            ]
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "pricing_calibration_issue" not in categories

    def test_underpricing_root_cause_label(self):
        result = _reason(signal_counts={"LIKELY_UNDERPRICING": 1})
        item = next(r for r in result["reasoning"] if r["category"] == "pricing_calibration_issue")
        assert "underpricing" in item["root_cause"].lower()

    def test_overpricing_root_cause_label(self):
        result = _reason(signal_counts={"LIKELY_OVERPRICING": 1})
        item = next(r for r in result["reasoning"] if r["category"] == "pricing_calibration_issue")
        assert "overpricing" in item["root_cause"].lower()


# ---------------------------------------------------------------------------
# operator_backlog
# ---------------------------------------------------------------------------


class TestOperatorBacklog:
    def test_review_rate_degrading_with_unhealthy_status(self):
        result = _reason(
            health_status="unhealthy",
            metric_trends=[_metric("review_rate", "degrading", "medium")],
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "operator_backlog" in categories

    def test_repeated_review_flag_signal(self):
        result = _reason(
            health_status="healthy",
            signal_counts={"REPEATED_REVIEW_FLAG": 3},
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "operator_backlog" in categories

    def test_review_degrading_healthy_no_signal_does_not_trigger(self):
        result = _reason(
            health_status="healthy",
            metric_trends=[_metric("review_rate", "degrading", "low")],
        )
        categories = [r["category"] for r in result["reasoning"]]
        assert "operator_backlog" not in categories


# ---------------------------------------------------------------------------
# mixed_or_unclear fallback
# ---------------------------------------------------------------------------


class TestMixedOrUnclear:
    def test_no_signals_returns_mixed(self):
        result = _reason(health_status="healthy", metric_trends=[], signal_counts={})
        assert result["reasoning"][0]["category"] == "mixed_or_unclear"

    def test_mixed_has_low_confidence(self):
        result = _reason(health_status="healthy")
        assert result["reasoning"][0]["confidence"] == "low"

    def test_mixed_has_recommendations(self):
        result = _reason()
        assert len(result["reasoning"][0]["recommendations"]) > 0


# ---------------------------------------------------------------------------
# Recommendation deduplication
# ---------------------------------------------------------------------------


class TestRecommendationDeduplication:
    def test_no_duplicate_recommendations_across_items(self):
        """When multiple rules fire, recommendations must not repeat globally."""
        result = _reason(
            health_status="unhealthy",
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "high"),
                _metric("review_rate", "degrading", "medium"),
                _metric("avg_confidence", "degrading", "medium"),
            ],
            signal_counts={
                "REPEATED_FALLBACK": 3,
                "REPEATED_REVIEW_FLAG": 2,
            },
        )
        all_recs = [rec for item in result["reasoning"] for rec in item["recommendations"]]
        assert len(all_recs) == len(set(all_recs)), "Duplicate recommendations found"


# ---------------------------------------------------------------------------
# Ordering — highest weight first
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_upstream_input_quality_before_operator_backlog(self):
        """upstream_input_quality has higher weight and should appear first."""
        result = _reason(
            health_status="unhealthy",
            metric_trends=[
                _metric("failed_rate", "degrading", "high"),
                _metric("fallback_rate", "degrading", "high"),
                _metric("review_rate", "degrading", "medium"),
            ],
            signal_counts={"REPEATED_REVIEW_FLAG": 2},
        )
        categories = [r["category"] for r in result["reasoning"]]
        uiq_idx = categories.index("upstream_input_quality")
        ob_idx = categories.index("operator_backlog")
        assert uiq_idx < ob_idx

    def test_scope_and_scope_id_preserved(self):
        result = _reason(scope_type="vertical", scope_id="painting")
        assert result["scope"] == "vertical"
        assert result["scope_id"] == "painting"
