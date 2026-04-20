#!/usr/bin/env python3
"""
Log in with email/password (form POST to /auth/login), capture the JWT from
the access_token cookie, then POST JSON from inversiq_payload.json to
/api/outreach/suggestions/bulk.

/api routes require HTTP Basic Auth (SALES_BASIC_AUTH_USER / SALES_BASIC_AUTH_PASS).
The session cookie from login is sent on the bulk request as well.

Environment variables (optional if you pass CLI flags):
  INVERSIQ_BASE_URL   default http://127.0.0.1:8000
  INVERSIQ_EMAIL
  INVERSIQ_PASSWORD
  SALES_BASIC_AUTH_USER
  SALES_BASIC_AUTH_PASS

Payload file (JSON) must look like:
  {"items": [
    {"company_name": "...", "recipient_email": "a@b.com",
     "subject": "...", "body": "...",
     "campaign_id": null, "variant_id": null}
  ]}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def login_and_get_token(
    session: requests.Session,
    base_url: str,
    email: str,
    password: str,
) -> str:
    login_url = f"{base_url.rstrip('/')}/auth/login"
    resp = session.post(
        login_url,
        data={"email": email, "password": password, "next": "/"},
        allow_redirects=True,
        timeout=60,
    )
    if resp.status_code >= 400:
        _die(f"Login HTTP {resp.status_code}: {resp.text[:2000]!r}")

    token = session.cookies.get("access_token")
    if not token:
        final = getattr(resp, "url", "") or ""
        if "error=1" in final or "error=1" in (resp.headers.get("Location") or ""):
            _die("Login failed: invalid email or password (no access_token cookie).")
        _die(
            "Login succeeded but no access_token cookie was set. "
            "Check base URL and that /auth/login matches this app."
        )
    return str(token)


def post_bulk(
    session: requests.Session,
    base_url: str,
    basic_user: str,
    basic_pass: str,
    payload: dict,
) -> requests.Response:
    bulk_url = f"{base_url.rstrip('/')}/api/outreach/suggestions/bulk"
    return session.post(
        bulk_url,
        json=payload,
        auth=(basic_user, basic_pass),
        headers={"Accept": "application/json"},
        timeout=120,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default=os.environ.get("INVERSIQ_BASE_URL", "http://127.0.0.1:8000"),
        help="API origin (no trailing slash required)",
    )
    p.add_argument("--email", default=os.environ.get("INVERSIQ_EMAIL", ""))
    p.add_argument("--password", default=os.environ.get("INVERSIQ_PASSWORD", ""))
    p.add_argument(
        "--payload",
        type=Path,
        default=Path("inversiq_payload.json"),
        help="Path to JSON body (default: ./inversiq_payload.json)",
    )
    args = p.parse_args()

    basic_user = os.environ.get("SALES_BASIC_AUTH_USER", "")
    basic_pass = os.environ.get("SALES_BASIC_AUTH_PASS", "")
    if not basic_user or not basic_pass:
        _die(
            "Set SALES_BASIC_AUTH_USER and SALES_BASIC_AUTH_PASS in the environment "
            "(required for /api/* Basic Auth middleware)."
        )

    if not args.email or not args.password:
        _die("Provide --email / --password or set INVERSIQ_EMAIL / INVERSIQ_PASSWORD.")

    if not args.payload.is_file():
        _die(f"Payload file not found: {args.payload.resolve()}")

    try:
        raw = args.payload.read_text(encoding="utf-8")
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        _die(f"Invalid JSON in {args.payload}: {e}")

    if not isinstance(body, dict) or "items" not in body:
        _die('Payload must be a JSON object with an "items" array (see script docstring).')

    session = requests.Session()

    try:
        token = login_and_get_token(session, args.base_url, args.email, args.password)
    except requests.RequestException as e:
        _die(f"Login request failed: {e}")

    print("JWT access token (from access_token cookie):")
    print(token)
    print()

    try:
        resp = post_bulk(session, args.base_url, basic_user, basic_pass, body)
    except requests.RequestException as e:
        _die(f"Bulk request failed: {e}")

    print(f"POST /api/outreach/suggestions/bulk -> HTTP {resp.status_code}")
    ct = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ct:
        try:
            print(json.dumps(resp.json(), indent=2, default=str))
        except ValueError:
            print(resp.text)
    else:
        print(resp.text[:8000] if resp.text else "(empty body)")

    if resp.status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
