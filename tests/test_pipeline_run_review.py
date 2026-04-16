"""
tests/test_pipeline_run_review.py

Unit tests for app.anomaly.run_review.compute_run_review.

The function is pure — no DB, no HTTP.  Tests pass kwargs directly and assert
on the returned dict.  Each scenario maps to one explicit rule in the module.

Scenarios covered
-----------------
FAILED status
  - permanent/validation error  → recommended, priority=high
  - transient error             → recommended, priority=medium
  - external_dependency error   → recommended, priority=medium
  - unknown error category      → recommended, priority=medium
  - overrides anomaly signals   (FAILED beats high-severity anomaly rule)

Anomaly-driven rules (status=COMPLETED)
  - high-severity flagged anomaly         → recommended, priority=high
  - high-severity NOT flagged (review_recommended=False) → not triggered
  - medium-severity flagged anomaly       → recommended, priority=medium
  - low-severity flagged anomaly          → recommended, priority=low
  - multiple severities — highest wins    (high beats medium and low)
  - anomalies without review_recommended  → ignored

Confidence-driven rule (status=COMPLETED, no anomalies)
  - overall_confidence_label="low"        → recommended, priority=medium
  - overall_confidence_label="medium"     → not triggered by this rule
  - overall_confidence_label="high"       → not triggered by this rule
  - overall_confidence_label=None         → not triggered by this rule

NEEDS_REVIEW status (no anomalies, healthy confidence)
  - recommended, priority=low
  - anomaly present can raise priority above low

Default / healthy run
  - COMPLETED, no anomalies, confidence OK → not recommended, priority=None
  - reason string is present and non-empty in all cases

Output shape
  - all three keys always present
"""

from __future__ import annotations

from typing import Any

import pytest

from app.anomaly.run_review import compute_run_review


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anomaly(
    *,
    severity: str,
    review_recommended: bool = True,
    action_hint: str = "do something",
) -> dict[str, Any]:
    """Minimal anomaly dict — only the fields compute_run_review inspects."""
    return {
        "severity": severity,
        "review_recommended": review_recommended,
        "action_hint": action_hint,
    }


def _call(
    *,
    status: str = "COMPLETED",
    error_category: str | None = None,
    overall_confidence_label: str | None = None,
    anomaly_dicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return compute_run_review(
        status=status,
        error_category=error_category,
        overall_confidence_label=overall_confidence_label,
        anomaly_dicts=anomaly_dicts or [],
    )


# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_all_keys_present_on_healthy_run(self):
        result = _call(status="COMPLETED")
        assert "review_recommended" in result
        assert "review_reason" in result
        assert "review_priority" in result

    def test_reason_is_always_non_empty_string(self):
        for status in ("COMPLETED", "FAILED", "NEEDS_REVIEW"):
            result = _call(status=status)
            assert isinstance(result["review_reason"], str)
            assert result["review_reason"].strip() != ""

    def test_review_recommended_is_bool(self):
        result = _call(status="COMPLETED")
        assert isinstance(result["review_recommended"], bool)

    def test_priority_none_when_not_recommended(self):
        result = _call(status="COMPLETED")
        assert result["review_recommended"] is False
        assert result["review_priority"] is None


# ---------------------------------------------------------------------------
# Rule 1-3: FAILED runs
# ---------------------------------------------------------------------------

class TestFailedRuns:
    def test_permanent_error_is_high_priority(self):
        result = _call(status="FAILED", error_category="permanent")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "high"
        assert "permanent" in result["review_reason"]

    def test_validation_error_is_high_priority(self):
        result = _call(status="FAILED", error_category="validation")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "high"
        assert "validation" in result["review_reason"]

    def test_transient_error_is_medium_priority(self):
        result = _call(status="FAILED", error_category="transient")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "medium"

    def test_external_dependency_is_medium_priority(self):
        result = _call(status="FAILED", error_category="external_dependency")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "medium"

    def test_unknown_category_is_medium_priority(self):
        result = _call(status="FAILED", error_category=None)
        assert result["review_recommended"] is True
        assert result["review_priority"] == "medium"

    def test_failed_beats_high_severity_anomaly(self):
        """FAILED (transient) → medium priority even if a high-sev anomaly is present.
        The FAILED rule fires first; anomaly rule is never reached."""
        result = _call(
            status="FAILED",
            error_category="transient",
            anomaly_dicts=[_anomaly(severity="high")],
        )
        assert result["review_recommended"] is True
        # Priority is medium (from transient), NOT high from anomaly
        assert result["review_priority"] == "medium"

    def test_failed_permanent_beats_anomaly_too(self):
        """FAILED (permanent) → high priority regardless of anomaly list."""
        result = _call(
            status="FAILED",
            error_category="permanent",
            anomaly_dicts=[_anomaly(severity="low")],
        )
        assert result["review_priority"] == "high"
        assert "permanent" in result["review_reason"]


# ---------------------------------------------------------------------------
# Rule 4: High-severity anomaly
# ---------------------------------------------------------------------------

class TestHighSeverityAnomaly:
    def test_high_severity_flagged_anomaly_triggers_high_priority(self):
        result = _call(anomaly_dicts=[_anomaly(severity="high", action_hint="urgent fix needed")])
        assert result["review_recommended"] is True
        assert result["review_priority"] == "high"
        assert "urgent fix needed" in result["review_reason"]

    def test_high_severity_not_flagged_does_not_trigger(self):
        """review_recommended=False on the anomaly means it should NOT raise a run-level flag."""
        result = _call(anomaly_dicts=[_anomaly(severity="high", review_recommended=False)])
        assert result["review_recommended"] is False


# ---------------------------------------------------------------------------
# Rule 5: Low overall confidence
# ---------------------------------------------------------------------------

class TestLowConfidence:
    def test_low_confidence_label_triggers_medium(self):
        result = _call(overall_confidence_label="low")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "medium"
        assert "confidence" in result["review_reason"].lower()

    def test_medium_confidence_label_does_not_trigger(self):
        result = _call(overall_confidence_label="medium")
        assert result["review_recommended"] is False

    def test_high_confidence_label_does_not_trigger(self):
        result = _call(overall_confidence_label="high")
        assert result["review_recommended"] is False

    def test_none_confidence_label_does_not_trigger(self):
        result = _call(overall_confidence_label=None)
        assert result["review_recommended"] is False


# ---------------------------------------------------------------------------
# Rule 6: Medium-severity anomaly
# ---------------------------------------------------------------------------

class TestMediumSeverityAnomaly:
    def test_medium_severity_flagged_triggers_medium_priority(self):
        result = _call(anomaly_dicts=[_anomaly(severity="medium", action_hint="check this step")])
        assert result["review_recommended"] is True
        assert result["review_priority"] == "medium"
        assert "check this step" in result["review_reason"]

    def test_medium_severity_not_flagged_is_ignored(self):
        result = _call(anomaly_dicts=[_anomaly(severity="medium", review_recommended=False)])
        assert result["review_recommended"] is False


# ---------------------------------------------------------------------------
# Rule 7: NEEDS_REVIEW status
# ---------------------------------------------------------------------------

class TestNeedsReviewStatus:
    def test_needs_review_status_triggers_low_priority(self):
        result = _call(status="NEEDS_REVIEW")
        assert result["review_recommended"] is True
        assert result["review_priority"] == "low"

    def test_needs_review_with_high_anomaly_is_high(self):
        """A high-sev anomaly fires before the NEEDS_REVIEW status rule → priority=high."""
        result = _call(
            status="NEEDS_REVIEW",
            anomaly_dicts=[_anomaly(severity="high")],
        )
        assert result["review_priority"] == "high"


# ---------------------------------------------------------------------------
# Rule 8: Low-severity anomaly
# ---------------------------------------------------------------------------

class TestLowSeverityAnomaly:
    def test_low_severity_flagged_triggers_low_priority(self):
        result = _call(anomaly_dicts=[_anomaly(severity="low", action_hint="minor gap")])
        assert result["review_recommended"] is True
        assert result["review_priority"] == "low"
        assert "minor gap" in result["review_reason"]

    def test_low_severity_not_flagged_is_ignored(self):
        result = _call(anomaly_dicts=[_anomaly(severity="low", review_recommended=False)])
        assert result["review_recommended"] is False


# ---------------------------------------------------------------------------
# Priority ordering across multiple anomalies
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    def test_high_beats_medium_and_low(self):
        result = _call(
            anomaly_dicts=[
                _anomaly(severity="low", action_hint="low hint"),
                _anomaly(severity="medium", action_hint="medium hint"),
                _anomaly(severity="high", action_hint="high hint"),
            ]
        )
        assert result["review_priority"] == "high"
        assert "high hint" in result["review_reason"]

    def test_medium_beats_low(self):
        result = _call(
            anomaly_dicts=[
                _anomaly(severity="low", action_hint="low hint"),
                _anomaly(severity="medium", action_hint="medium hint"),
            ]
        )
        assert result["review_priority"] == "medium"
        assert "medium hint" in result["review_reason"]

    def test_low_confidence_beats_medium_anomaly_at_same_level(self):
        """Low confidence (rule 5) and a medium anomaly (rule 6) both produce medium.
        Low confidence fires first since it's checked before medium anomalies."""
        result = _call(
            overall_confidence_label="low",
            anomaly_dicts=[_anomaly(severity="medium", action_hint="medium anomaly")],
        )
        assert result["review_priority"] == "medium"
        # reason should mention confidence, not the anomaly (first rule wins)
        assert "confidence" in result["review_reason"].lower()


# ---------------------------------------------------------------------------
# Default: healthy run
# ---------------------------------------------------------------------------

class TestHealthyRun:
    def test_completed_no_anomalies_is_clean(self):
        result = _call(status="COMPLETED", overall_confidence_label="high")
        assert result["review_recommended"] is False
        assert result["review_priority"] is None
        assert result["review_reason"]

    def test_empty_anomaly_list_is_clean(self):
        result = _call(status="COMPLETED", anomaly_dicts=[])
        assert result["review_recommended"] is False

    def test_anomalies_with_review_false_are_all_ignored(self):
        """All three severities present, none flagged for review → clean."""
        result = _call(
            anomaly_dicts=[
                _anomaly(severity="high", review_recommended=False),
                _anomaly(severity="medium", review_recommended=False),
                _anomaly(severity="low", review_recommended=False),
            ]
        )
        assert result["review_recommended"] is False
        assert result["review_priority"] is None
