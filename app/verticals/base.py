from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseVertical(ABC):
    """
    Abstract contract for all industry vertical implementations.

    Every vertical (e.g. construction, insurance, logistics, real_estate) must provide a
    stable key, a human-readable label, workflow definitions, dashboard config,
    and feature metadata.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique machine-readable identifier for the vertical."""
        raise NotImplementedError

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable display name for the vertical."""
        raise NotImplementedError

    @abstractmethod
    def get_workflows(self) -> list[dict[str, Any]]:
        """Return engine pipeline step descriptors for this vertical."""
        raise NotImplementedError

    def get_engine_pipeline(self) -> list[dict[str, Any]]:
        """
        Return internal engine pipeline steps.

        Defaults to `get_workflows()` for backward compatibility with existing
        vertical implementations and engine callers.
        """
        return self.get_workflows()

    def get_ui_workflows(self) -> list[str]:
        """
        Return high-level user-facing workflow stages for UI display.

        Defaults to an empty list so existing verticals can opt in explicitly.
        """
        return []

    @abstractmethod
    def get_dashboard_config(self) -> dict[str, Any]:
        """Return dashboard UI and data configuration for this vertical."""
        raise NotImplementedError

    @abstractmethod
    def get_features(self) -> dict[str, Any]:
        """Return feature flags and capability metadata for this vertical."""
        raise NotImplementedError
