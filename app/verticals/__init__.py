from __future__ import annotations

from app.verticals.registry import register
from app.verticals.registry import VERTICALS


def register_verticals(app=None) -> None:
    # Lazy import prevents circular import during engine step module initialization.
    import app.verticals.construction  # noqa: F401
    from app.verticals.construction.adapter import ConstructionAdapter

    if "construction" not in VERTICALS:
        register(ConstructionAdapter())
