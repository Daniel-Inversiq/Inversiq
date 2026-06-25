from __future__ import annotations

from typing import Any

from app.verticals.base import BaseVertical
from app.verticals.registry import VERTICALS, register_vertical


class RoofingVertical(BaseVertical):
    """Roofing-specific vertical configuration and capabilities."""

    @property
    def key(self) -> str:
        return "roofing"

    @property
    def label(self) -> str:
        return "Dakwerk"

    def get_workflows(self) -> list[dict[str, Any]]:
        return [
            {"id": "estimate", "use": "roofing.estimate.v1"},
            {
                "id": "review",
                "use": "roofing.review.v1",
                "on_needs_review": "CONTINUE",
            },
            {"id": "store", "use": "roofing.store.v1"},
        ]

    def get_ui_workflows(self) -> list[str]:
        return ["intake", "inspectie", "offerte"]

    def get_dashboard_config(self) -> dict[str, Any]:
        return {
            "show_kpis": True,
            "show_pipeline": True,
            "show_recent_jobs": True,
        }

    def get_features(self) -> dict[str, Any]:
        return {
            "measurements": True,
            "damage_assessment": True,
            "solar_estimation": False,
        }


if "roofing" not in VERTICALS:
    register_vertical(RoofingVertical())


__all__ = ["RoofingVertical"]
