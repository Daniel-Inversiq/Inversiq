from __future__ import annotations

from typing import Any

from app.verticals.base import BaseVertical
from app.verticals.registry import VERTICALS, register_vertical


class SolarVertical(BaseVertical):
    """Solar-specific vertical configuration and capabilities."""

    @property
    def key(self) -> str:
        return "solar"

    @property
    def label(self) -> str:
        return "Zonnepanelen"

    def get_workflows(self) -> list[dict[str, Any]]:
        return [
            {"id": "quote", "use": "solar.quote.v1"},
            {
                "id": "review",
                "use": "solar.review.v1",
                "on_needs_review": "CONTINUE",
            },
            {"id": "save", "use": "solar.save.v1"},
        ]

    def get_ui_workflows(self) -> list[str]:
        return ["intake", "analyse", "offerte"]

    def get_dashboard_config(self) -> dict[str, Any]:
        return {
            "show_kpis": True,
            "show_pipeline": True,
            "show_recent_jobs": True,
        }

    def get_features(self) -> dict[str, Any]:
        return {
            "measurements": False,
            "damage_assessment": False,
            "solar_estimation": True,
        }


if "solar" not in VERTICALS:
    register_vertical(SolarVertical())


__all__ = ["SolarVertical"]
