from __future__ import annotations

from app.verticals.registry import register


def register_verticals(app=None) -> None:
    # Lazy import prevents circular import during engine step module initialization.
    from app.verticals.painting.adapter import PaintlyAdapter
    from app.verticals.roofing.adapter import RoofingAdapter

    # Paintly EU-first vertical
    register(
        PaintlyAdapter(),
        aliases=["painters_us"],   # backward compatibility
    )

    # Roofing vertical (intake form not yet wired; adapter registered for future use)
    register(RoofingAdapter())

    # Solar vertical (intake form not yet wired; adapter registered for future use)
    from app.verticals.solar.adapter import SolarAdapter
    register(SolarAdapter())