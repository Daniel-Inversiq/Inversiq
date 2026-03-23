from __future__ import annotations

from app.verticals.registry import register


def register_verticals(app=None) -> None:
    # Lazy import prevents circular import during engine step module initialization.
    from app.verticals.paintly.adapter import PaintlyAdapter

    # Paintly EU-first vertical
    register(
        PaintlyAdapter(),
        aliases=["painters_us"],   # backward compatibility
    )