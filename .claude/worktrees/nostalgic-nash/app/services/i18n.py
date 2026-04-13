"""
Deprecated: Flask-oriented i18n module.

The app now uses FastAPI-native i18n in `app.i18n.service`.
Kept as a thin compatibility wrapper to avoid import breakage.
"""

from app.i18n.service import DEFAULT_LANG, resolve_language, translate

__all__ = ["DEFAULT_LANG", "resolve_language", "translate"]
