from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

DEFAULT_LANG = "nl"
SUPPORTED_LANGS = {"nl", "en"}
COOKIE_NAME = "lang"
I18N_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _load_catalogs() -> dict[str, dict[str, Any]]:
    catalogs: dict[str, dict[str, Any]] = {}
    for lang in SUPPORTED_LANGS:
        path = I18N_DIR / f"{lang}.json"
        with path.open("r", encoding="utf-8") as fh:
            catalogs[lang] = json.load(fh)
    return catalogs


def _normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    base = code.lower().split(",")[0].split("-")[0].split("_")[0].strip()
    return base if base else None


def _pick_from_accept_language(header: str | None) -> str | None:
    if not header:
        return None

    weighted: list[tuple[float, str]] = []
    for part in header.split(","):
        token = part.strip()
        if not token:
            continue
        q = 1.0
        if ";" in token:
            raw_lang, *params = token.split(";")
            token = raw_lang.strip()
            for p in params:
                p = p.strip().lower()
                if p.startswith("q="):
                    try:
                        q = float(p[2:])
                    except ValueError:
                        q = 1.0
        lang = _normalize_lang(token)
        if lang in SUPPORTED_LANGS:
            weighted.append((q, lang))

    if not weighted:
        return None
    weighted.sort(reverse=True)
    return weighted[0][1]


def resolve_language(request: Request, fallback: str = DEFAULT_LANG) -> str:
    """
    Resolve language with simple priority:
    1) ?lang=xx
    2) cookie: lang
    3) Accept-Language header
    4) fallback (nl)
    """
    q_lang = _normalize_lang(request.query_params.get("lang"))
    if q_lang in SUPPORTED_LANGS:
        return q_lang

    cookie_lang = _normalize_lang(request.cookies.get(COOKIE_NAME))
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang

    header_lang = _pick_from_accept_language(request.headers.get("Accept-Language"))
    if header_lang in SUPPORTED_LANGS:
        return header_lang

    return fallback


def set_language_cookie(response: Any, lang: str) -> None:
    safe_lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    response.set_cookie(COOKIE_NAME, safe_lang, max_age=60 * 60 * 24 * 365, samesite="lax")


def _lookup_key(catalog: dict[str, Any], key: str) -> str | None:
    current: Any = catalog
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]
    return current if isinstance(current, str) else None


def translate(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    catalogs = _load_catalogs()
    safe_lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG

    text = _lookup_key(catalogs.get(safe_lang, {}), key)
    if text is None and safe_lang != DEFAULT_LANG:
        text = _lookup_key(catalogs.get(DEFAULT_LANG, {}), key)
    if text is None:
        return key

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


@pass_context
def template_translate(context: dict[str, Any], key: str, **kwargs: Any) -> str:
    request = context.get("request")
    lang = DEFAULT_LANG
    if isinstance(request, Request):
        lang = resolve_language(request)
    return translate(key, lang=lang, **kwargs)


def setup_jinja_i18n(templates: Jinja2Templates) -> None:
    templates.env.globals["t"] = template_translate
