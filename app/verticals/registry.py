from __future__ import annotations

from app.core.contracts import VerticalAdapter
from app.verticals.base import BaseVertical


class VerticalNotFoundError(KeyError):
    """Raised when a requested vertical is not present in the registry."""


VERTICALS: dict[str, BaseVertical | VerticalAdapter] = {}
_ALIASES: dict[str, str] = {}  # alias -> canonical key


def _resolve_vertical_key(vertical: BaseVertical | VerticalAdapter) -> str:
    if isinstance(vertical, BaseVertical):
        key = vertical.key
    else:
        key = vertical.vertical_id

    if not key:
        raise ValueError("Vertical key is required")
    return key


def _register_internal(vertical: BaseVertical | VerticalAdapter) -> None:
    key = _resolve_vertical_key(vertical)

    if key in VERTICALS:
        raise ValueError(f"Vertical already registered: {key}")

    VERTICALS[key] = vertical


def register_vertical(vertical: BaseVertical) -> None:
    _register_internal(vertical)


def get_vertical(key: str) -> BaseVertical | VerticalAdapter:
    resolved_key = _ALIASES.get(key, key)
    vertical = VERTICALS.get(resolved_key)
    if vertical is None:
        available = ", ".join(sorted(VERTICALS.keys())) or "none"
        aliases = ", ".join(sorted(_ALIASES.keys())) or "none"
        raise VerticalNotFoundError(
            f"Vertical '{key}' not found. Available verticals: [{available}]. "
            f"Available aliases: [{aliases}]."
        )
    return vertical


# Backward-compatible API wrappers used by existing modules.
def register(adapter: VerticalAdapter, aliases: list[str] | None = None) -> None:
    key = _resolve_vertical_key(adapter)
    _register_internal(adapter)

    if aliases:
        for alias in aliases:
            _ALIASES[alias] = key


def get(vertical_id: str) -> BaseVertical | VerticalAdapter:
    return get_vertical(vertical_id)
