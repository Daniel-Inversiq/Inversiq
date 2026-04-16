"""
Run-level review recommendation.

Pure function — no DB calls, no side effects.  Given the run's status,
confidence label, error category, and the anomaly dicts already computed
for that run, returns a deterministic review decision.

Rules are explicit and evaluated in priority order: the first matching rule
wins.  This makes the logic easy to read, test, and extend without touching
the rest of the engine.

Output shape
------------
{
    "review_recommended": bool,
    "review_reason":      str,
    "review_priority":    "low" | "medium" | "high" | None,
}

Priority mapping (highest first)
---------------------------------
1. FAILED + permanent/validation error        → high
2. FAILED + transient/external error          → medium
3. FAILED + unknown error category            → medium
4. Any high-severity anomaly flagged for review → high
5. Overall confidence label is "low"          → medium
6. Any medium-severity anomaly flagged        → medium
7. Status is explicitly NEEDS_REVIEW          → low
8. Any low-severity anomaly flagged           → low
9. No trigger matched                         → not recommended / None priority
"""

from __future__ import annotations

from typing import Any, Optional


def compute_run_review(
    *,
    status: str,
    error_category: Optional[str],
    overall_confidence_label: Optional[str],
    anomaly_dicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute a run-level review recommendation from existing signals.

    Parameters
    ----------
    status                   : PipelineRun.status
    error_category           : PipelineRun.error_category (nullable)
    overall_confidence_label : PipelineRun.overall_confidence_label (nullable)
    anomaly_dicts            : List of anomaly .to_dict() results for this run.

    Returns
    -------
    dict with keys: review_recommended (bool), review_reason (str),
    review_priority ("low" | "medium" | "high" | None)
    """
    # ------------------------------------------------------------------
    # Rule 1-3: FAILED run — always recommend review; priority depends on
    # error_category because that determines whether a retry is safe.
    # ------------------------------------------------------------------
    if status == "FAILED":
        ec = (error_category or "").lower()
        if ec in ("permanent", "validation"):
            return _decide(
                True, "high",
                f"Run failed with a {ec} error — investigate root cause before retrying.",
            )
        if ec in ("transient", "external_dependency"):
            return _decide(
                True, "medium",
                "Run failed on a likely transient error — verify root cause before retrying.",
            )
        return _decide(
            True, "medium",
            "Run failed — error category is unknown, treat as non-retryable until investigated.",
        )

    # ------------------------------------------------------------------
    # Rule 4: Any high-severity anomaly that was individually flagged for
    # review elevates to run-level high priority.
    # ------------------------------------------------------------------
    hit = _first_actionable(anomaly_dicts, severity="high")
    if hit:
        return _decide(True, "high", f"High-severity anomaly detected: {hit['action_hint']}")

    # ------------------------------------------------------------------
    # Rule 5: Low overall confidence on a COMPLETED run means the outputs
    # are unreliable even though no step explicitly failed.
    # ------------------------------------------------------------------
    if overall_confidence_label == "low":
        return _decide(
            True, "medium",
            "Overall pipeline confidence is low — outputs may be unreliable.",
        )

    # ------------------------------------------------------------------
    # Rule 6: Medium-severity anomaly flagged for review.
    # ------------------------------------------------------------------
    hit = _first_actionable(anomaly_dicts, severity="medium")
    if hit:
        return _decide(True, "medium", f"Medium-severity anomaly detected: {hit['action_hint']}")

    # ------------------------------------------------------------------
    # Rule 7: Run was explicitly placed in NEEDS_REVIEW by the engine.
    # Checked after anomaly rules so anomaly severity can raise the bar.
    # ------------------------------------------------------------------
    if status == "NEEDS_REVIEW":
        return _decide(True, "low", "Run was explicitly marked NEEDS_REVIEW by the engine.")

    # ------------------------------------------------------------------
    # Rule 8: Low-severity anomaly flagged for review.
    # ------------------------------------------------------------------
    hit = _first_actionable(anomaly_dicts, severity="low")
    if hit:
        return _decide(True, "low", f"Low-severity anomaly detected: {hit['action_hint']}")

    # ------------------------------------------------------------------
    # Default: no trigger matched.
    # ------------------------------------------------------------------
    return _decide(False, None, "No review triggers matched — run appears healthy.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _first_actionable(
    anomaly_dicts: list[dict[str, Any]],
    *,
    severity: str,
) -> Optional[dict[str, Any]]:
    """Return the first anomaly dict with review_recommended=True at *severity*."""
    return next(
        (
            a for a in anomaly_dicts
            if a.get("review_recommended") and a.get("severity") == severity
        ),
        None,
    )


def _decide(
    recommended: bool,
    priority: Optional[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "review_recommended": recommended,
        "review_reason": reason,
        "review_priority": priority,
    }
