"""
app/verticals/painting/__init__.py

Public surface for the painting (paintly) vertical.

This module declares the two stable entry points that the rest of the
application uses to interact with the painting vertical:

  PaintlyAdapter          — HTTP-layer adapter; implements VerticalAdapter.
                            Registered in app/verticals/__init__.py and used
                            by the uploads and intake routers.

  compute_and_persist_quote — Quote service function; runs the engine,
                              persists the result, returns a summary dict.
                              Called only by PaintlyAdapter.compute_quote().

Internal modules (importable but not part of the stable surface)
----------------------------------------------------------------
  pipeline              — Legacy pipeline; compute_quote_for_lead is re-exported
                          below for external callers (debug routers).  Internal
                          to the vertical; will eventually be replaced by
                          quote_service + the v15 engine path.
  pricing_engine_us     — EU/US pricing math.  Internal compute layer.
  pricing_output_builder — Estimate output builder.  Internal compute layer.
  vision_aggregate_us   — Vision aggregation.  Internal compute layer.
  needs_review          — Review routing decision.  Internal compute layer.
  render_estimate       — HTML estimate renderer.  Internal.
  eu_config             — EU configuration resolver.  Internal.
  email_render          — Email template rendering.  Internal.
  calendar_ics          — ICS calendar payload builder.  Internal.
  google_calendar_*     — Google Calendar integration.  Internal.
  estimate_email        — Estimate email orchestration.  Internal.

Pending coupling to resolve (tracked, not fixed here)
------------------------------------------------------
  inversiq/engine/steps/paintly_steps.py imports five painting compute
  modules directly (pricing_engine_us, pricing_output_builder,
  vision_aggregate_us, render_estimate, needs_review).  These should
  eventually be accessed through this public surface rather than
  directly, once the engine extraction phase begins.
"""

# Stable orchestration entry points
from app.verticals.painting.adapter import PaintlyAdapter
from app.verticals.painting.quote_service import compute_and_persist_quote

# Legacy pipeline entry point — compute-only (no DB persist), returns
# estimate_json as dict.  Used by debug routers; internal router_app.py
# callers import lazily from the submodule directly.
# Do not use for new code — prefer compute_and_persist_quote.
from app.verticals.painting.pipeline import compute_quote_for_lead

# Pure compute helper — used by debug routes for post-hoc review inspection.
from app.verticals.painting.needs_review import needs_review_from_output

__all__ = [
    # Stable
    "PaintlyAdapter",
    "compute_and_persist_quote",
    # Legacy / debug surface
    "compute_quote_for_lead",
    "needs_review_from_output",
]
