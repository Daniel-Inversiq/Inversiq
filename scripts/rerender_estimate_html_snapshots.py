# scripts/rerender_estimate_html_snapshots.py
"""
Re-materialize stored estimate HTML from lead.estimate_json (current Jinja templates).

Use when estimate.html / public customer shell output changed but you do not want a full
AI/pipeline rerun. Does not change estimate_json.

Examples:
  python -m scripts.rerender_estimate_html_snapshots --lead-id <uuid>
  python -m scripts.rerender_estimate_html_snapshots --tenant-id <uuid> --all
  python -m scripts.rerender_estimate_html_snapshots --tenant-id <uuid> --all --dry-run
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lead-id", help="Single lead ID to rerender")
    parser.add_argument("--tenant-id", help="Tenant ID (required with --all)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="All leads in tenant that have non-empty estimate_json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List leads that would be updated, no writes",
    )
    args = parser.parse_args()

    if not args.lead_id and not args.all:
        parser.error("Provide --lead-id or --all")
    if args.all and not args.tenant_id:
        parser.error("--tenant-id is required with --all")

    from app.db import SessionLocal
    from app.models.lead import Lead
    from app.verticals.construction.router_app import rerender_stored_estimate_html_from_json

    db = SessionLocal()
    try:
        if args.lead_id:
            lead = db.query(Lead).filter(Lead.id == args.lead_id).first()
            if not lead:
                print("Lead not found", file=sys.stderr)
                return 1
            if args.dry_run:
                print(f"dry-run: would rerender lead_id={lead.id} tenant_id={lead.tenant_id}")
                return 0
            ok, err = rerender_stored_estimate_html_from_json(db, lead)
            if not ok:
                print(f"failed: {err}", file=sys.stderr)
                return 1
            print(f"ok lead_id={lead.id} estimate_html_key={lead.estimate_html_key!r}")
            return 0

        leads = (
            db.query(Lead)
            .filter(
                Lead.tenant_id == args.tenant_id,
                Lead.estimate_json.isnot(None),  # type: ignore[union-attr]
            )
            .all()
        )
        todo = [L for L in leads if isinstance(L.estimate_json, str) and L.estimate_json.strip()]
        print(f"tenant_id={args.tenant_id} leads_with_json={len(todo)}")
        if args.dry_run:
            for L in todo:
                print(f"  dry-run lead_id={L.id} html_key={getattr(L, 'estimate_html_key', None)!r}")
            return 0
        ok_c = 0
        fail_c = 0
        for L in todo:
            ok, err = rerender_stored_estimate_html_from_json(db, L)
            if ok:
                ok_c += 1
                print(f"ok lead_id={L.id}")
            else:
                fail_c += 1
                print(f"FAIL lead_id={L.id} err={err}", file=sys.stderr)
        print(f"done ok={ok_c} fail={fail_c}")
        return 0 if fail_c == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
