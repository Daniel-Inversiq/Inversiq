"""Public surface and vertical definition for the construction industry."""

from __future__ import annotations

from typing import Any

from app.verticals.construction.adapter import ConstructionAdapter
from app.verticals.base import BaseVertical
from app.verticals.construction.needs_review import needs_review_from_output
from app.verticals.construction.pipeline import compute_quote_for_lead
from app.verticals.construction.quote_service import compute_and_persist_quote
from app.verticals.registry import VERTICALS, register_vertical


class ConstructionVertical(BaseVertical):
    """Construction vertical configuration and capabilities."""

    @property
    def key(self) -> str:
        return "construction"

    @property
    def label(self) -> str:
        return "Construction"

    def get_workflows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "photo_quality",
                "use": "photo_quality.v1",
                "with": {"min_confidence": 0.65},
            },
            {"id": "vision", "use": "vision.v1"},
            {"id": "aggregate", "use": "aggregate.v1"},
            {"id": "pricing", "use": "pricing.v1"},
            {"id": "output", "use": "output.v1"},
            {
                "id": "needs_review",
                "use": "needs_review.v1",
                "on_needs_review": "CONTINUE",
            },
            {"id": "render_html", "use": "render.v1"},
            {"id": "store_html", "use": "store_html.v1"},
        ]

    def get_ui_workflows(self) -> list[str]:
        return ["intake", "review", "estimate"]

    def get_dashboard_config(self) -> dict[str, Any]:
        return {
            "show_kpis": True,
            "show_pipeline": True,
            "show_recent_jobs": True,
        }

    def get_features(self) -> dict[str, Any]:
        return {
            "measurements": True,
            "damage_assessment": False,
            "yield_estimation": False,
        }


if "construction" not in VERTICALS:
    register_vertical(ConstructionVertical())

__all__ = [
    "ConstructionVertical",
    "ConstructionAdapter",
    "compute_and_persist_quote",
    "compute_quote_for_lead",
    "needs_review_from_output",
]
