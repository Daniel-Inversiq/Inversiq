from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.verticals.construction.router_app import build_followup_summary
from app.verticals.construction.router_htmx import timeline_rows_for_lead


def test_timeline_rows_supports_english_labels() -> None:
    lead = SimpleNamespace(
        created_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        sent_at=None,
        viewed_at=None,
        status="NEW",
        accepted_at=None,
        updated_at=None,
        reject_reason=None,
    )

    rows = timeline_rows_for_lead(lead, "Europe/Amsterdam", lang="en")
    assert rows[0]["label"] == "Created"


def test_timeline_rows_rejected_includes_customer_note_label_en() -> None:
    lead = SimpleNamespace(
        created_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        sent_at=None,
        viewed_at=None,
        status="REJECTED",
        accepted_at=None,
        updated_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        reject_reason="Too expensive",
    )

    rows = timeline_rows_for_lead(lead, "Europe/Amsterdam", lang="en")
    labels = [row["label"] for row in rows]
    assert "Rejected" in labels
    assert "Customer note" in labels


def test_build_followup_summary_sets_status_code() -> None:
    now = datetime.now(timezone.utc) + timedelta(minutes=30)
    summary = build_followup_summary(
        {
            "next_action": "Call customer",
            "next_action_at": now.isoformat(),
        },
        "Europe/Amsterdam",
    )
    assert summary["has_followup"] is True
    assert summary["status_code"] in {"overdue", "today", "upcoming"}
