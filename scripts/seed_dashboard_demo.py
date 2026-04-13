# scripts/seed_dashboard_demo.py
"""
DEV-ONLY: Seed realistic demo leads + jobs so dashboard charts and KPIs are populated.

Usage:
    python -m scripts.seed_dashboard_demo --tenant-slug dev-tenant

Requires an existing tenant. Create one first with:
    python -m scripts.bootstrap_dev_auth

NOTE: This script APPENDS — re-running adds duplicates on a dev DB.
"""
from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db import SessionLocal
from app.models.job import Job
from app.models.lead import Lead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: float) -> datetime:
    return utcnow() - timedelta(days=n)


def make_estimate_json(amount: float) -> str:
    pre_tax = round(amount / 1.21, 2)
    return json.dumps({
        "totals": {
            "grand_total": round(amount, 2),
            "pre_tax": pre_tax,
            "tax": round(amount - pre_tax, 2),
        }
    })


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Thomas", "Lena", "Piet", "Marieke", "Koen", "Anneke", "Dirk", "Sofie",
    "Jeroen", "Fenna", "Rob", "Ingrid", "Bas", "Hanna", "Sander", "Miriam",
    "Willem", "Carla", "Frank", "Tessa", "Niek", "Joyce", "Arjan", "Nicole",
    "Erik", "Laura", "Stefan", "Eline", "Ruben", "Petra",
]

LAST_NAMES = [
    "Bakker", "de Vries", "Janssen", "Visser", "Smit", "Mulder", "Hendriks",
    "van den Berg", "Meijer", "Bos", "Vermeer", "Wolters", "de Jong", "Kuijpers",
    "Kok", "Hartman", "Prins", "Postma", "Bosman", "Groen", "Hoekstra", "Nijs",
    "Vos", "van Dijk", "Laan", "Peters", "Brouwer", "de Boer", "Jacobs", "Willems",
]

NOTES = [
    "Woonkamer + hal schilderen",
    "Buitenkant woning, 2 verdiepingen",
    "Slaapkamers en badkamer",
    "Kozijnen en deuren buiten",
    "Volledige woning intern",
    "Garage + schuur buitenkant",
    "Appartement volledig schilderen",
    "Verbouwing woonkamer + keuken",
    "Stucwerk + schilderwerk woonkamer",
    "Dak + gevelbekleding volledig",
    "Binnenwerk 3-kamer appartement",
    "Compleet huis schilderen",
    "Buitenschilderwerk vrijstaande woning",
    "Keuken + woonkamer schilderen",
    "Nieuwbouwwoning afwerking",
    "Dakkapel + gevel schilderen",
    "Gehele renovatie buitengevel",
    "Serre + aanbouw schilderen",
    "Magazijn binnenwerk schilderen",
    "Slaapkamers + overloop",
    "Bedrijfspand buitenkant",
    "Badkamer + toilet schilderen",
    "Verbouwingsproject uitgesteld",
    "Twee-onder-een-kap buitenschilderwerk",
    "Houten vloer + wanden behandelen",
]

REJECT_REASONS = [
    "Te duur vergeleken met andere offertes",
    "Klant gaat het zelf doen",
    "Geen reactie na meerdere pogingen",
    "Project uitgesteld door klant",
    "Gekozen voor andere aannemer",
]


def random_name(rng: random.Random) -> tuple[str, str, str]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    slug = f"{first.lower()}.{last.lower().replace(' ', '')}"
    email = f"{slug}{rng.randint(1, 99)}@demo.example"
    return f"{first} {last}", email, f"+31 6 {rng.randint(10000000, 99999999)}"


def spread_over_months(rng: random.Random, total: int) -> list[float]:
    """Return created_days_ago values spread roughly over last 6 months."""
    results = []
    # 6 months ≈ 180 days; distribute leads so each month gets some
    for i in range(total):
        # bias toward recent months but cover all 6
        month_bucket = rng.randint(0, 5)  # 0 = most recent, 5 = oldest
        base = month_bucket * 30
        jitter = rng.uniform(0, 28)
        results.append(base + jitter)
    return results


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------

def resolve_tenant_id(db, slug: str) -> str:
    row = db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug LIMIT 1"),
        {"slug": slug},
    ).fetchone()
    if not row:
        print(f"ERROR: No tenant found with slug '{slug}'.")
        print("       Run: python -m scripts.bootstrap_dev_auth  to create one first.")
        sys.exit(1)
    return str(row[0])


def seed(tenant_id: str, db) -> None:
    rng = random.Random(42)  # fixed seed for reproducible names/amounts
    now = utcnow()

    total_leads = 26
    ages = spread_over_months(rng, total_leads)
    ages.sort(reverse=True)  # oldest first

    # Status distribution across the 26 leads:
    # NEW: 4, SENT-recent: 3, SENT-overdue: 3, VIEWED: 4, ACCEPTED: 8, REJECTED: 4
    statuses = (
        ["NEW"] * 4
        + ["SENT_RECENT"] * 3
        + ["SENT_OVERDUE"] * 3
        + ["VIEWED"] * 4
        + ["ACCEPTED"] * 8
        + ["REJECTED"] * 4
    )
    rng.shuffle(statuses)

    leads_created = 0
    jobs_created = 0
    status_counts: dict[str, int] = {}

    for i, (age_days, raw_status) in enumerate(zip(ages, statuses)):
        name, email, phone = random_name(rng)
        note = rng.choice(NOTES)
        amount = round(rng.uniform(500, 8000) / 50) * 50  # round to nearest €50
        created_at = days_ago(age_days)

        # Resolve actual status and timestamps
        status: str
        sent_at = None
        viewed_at = None
        accepted_at = None
        reject_reason = None
        job_status = None
        job_scheduled_at = None
        job_done_at = None

        if raw_status == "NEW":
            status = "NEW"

        elif raw_status == "SENT_RECENT":
            status = "SENT"
            # sent 1–10 days ago (not overdue)
            sent_days = min(age_days - 0.5, rng.uniform(1, 10))
            sent_at = days_ago(sent_days)

        elif raw_status == "SENT_OVERDUE":
            status = "SENT"
            # sent 15–25 days ago (overdue — triggers follow-up logic)
            sent_days = min(age_days - 0.5, rng.uniform(15, 25))
            sent_at = days_ago(sent_days)

        elif raw_status == "VIEWED":
            status = "VIEWED"
            sent_days = min(age_days - 1, rng.uniform(5, 20))
            sent_at = days_ago(sent_days)
            viewed_days = min(sent_days - 0.5, rng.uniform(1, sent_days * 0.8))
            viewed_at = days_ago(viewed_days)

        elif raw_status == "ACCEPTED":
            status = "ACCEPTED"
            sent_days = min(age_days - 2, rng.uniform(5, 30))
            sent_at = days_ago(sent_days)
            # accepted 1–14 days after sending
            delta = rng.uniform(1, min(14, sent_days - 0.5))
            accepted_at = sent_at + timedelta(days=delta)

            # Job for accepted lead
            job_status = "DONE" if age_days > 45 else "NEW"
            if job_status == "NEW":
                job_scheduled_at = now + timedelta(days=rng.uniform(7, 30))
            else:
                done_days = max(1, age_days - rng.uniform(10, 30))
                job_done_at = days_ago(done_days)
                job_scheduled_at = job_done_at - timedelta(days=2)

        elif raw_status == "REJECTED":
            status = "REJECTED"
            sent_days = min(age_days - 1, rng.uniform(5, 25))
            sent_at = days_ago(sent_days)
            reject_reason = rng.choice(REJECT_REASONS)
            amount = round(rng.uniform(500, 5000) / 50) * 50

        lead = Lead(
            tenant_id=tenant_id,
            vertical="painters_nl",
            name=name,
            email=email,
            phone=phone,
            notes=note,
            status=status,
            created_at=created_at,
            final_price=amount,
            estimate_json=make_estimate_json(amount),
            public_token=secrets.token_hex(16),
            sent_at=sent_at,
            viewed_at=viewed_at,
            accepted_at=accepted_at,
            reject_reason=reject_reason,
        )

        db.add(lead)
        db.flush()  # get lead.id before FK reference
        leads_created += 1
        status_counts[status] = status_counts.get(status, 0) + 1

        if job_status:
            job = Job(
                tenant_id=tenant_id,
                lead_id=lead.id,
                status=job_status,
                scheduled_at=job_scheduled_at,
            )
            if job_status == "DONE" and job_done_at:
                job.started_at = job_done_at - timedelta(days=1)
                job.done_at = job_done_at
            db.add(job)
            jobs_created += 1

    db.commit()

    won = sum(
        t.final_price or 0
        for t in db.query(Lead)
        .filter(Lead.tenant_id == tenant_id, Lead.status == "ACCEPTED")
        .order_by(Lead.created_at.desc())
        .limit(total_leads)
        .all()
    )

    print(f"\n✅  Seeded {leads_created} leads + {jobs_created} jobs  (tenant: {tenant_id})")
    print("\n   Status breakdown:")
    for s in sorted(status_counts):
        print(f"     {s:<12}  {status_counts[s]}")
    print(f"\n   Dashboard: /app/dashboard   Leads: /app/leads")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="[DEV ONLY] Seed dashboard demo data for an existing tenant.",
        epilog=(
            "Example:\n"
            "  python -m scripts.seed_dashboard_demo --tenant-slug dev-tenant\n\n"
            "Appends to existing data. Re-running creates duplicates.\n"
            "To wipe first: python -m scripts.seed_reset"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tenant-slug",
        required=True,
        metavar="SLUG",
        help="Slug of the tenant to seed (see tenants.slug in the DB)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant_id = resolve_tenant_id(db, args.tenant_slug)
        print(f"Seeding demo data for tenant '{args.tenant_slug}'  (id={tenant_id})")
        seed(tenant_id, db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
