"""
scripts/seed_demo.py

Idempotent demo seed for the Delin CEO walkthrough.

Creates or resets:
  - A demo user   (demo@inversiq.com / Demo2025!)
  - A demo tenant (sector=construction, onboarding complete)
  - A workspace   "Basingstoke Logistics Park -- Delin Q2 2025"
    with 5 synthetic documents and 3 pre-seeded flags

Usage:
    python scripts/seed_demo.py

Safe to run repeatedly. No real Delin files needed. No LLM calls.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, engine, Base  # noqa: E402
from app.auth.passwords import hash_password   # noqa: E402
from app.models.tenant import Tenant           # noqa: E402
from app.models.user import User               # noqa: E402
from app.models.workspace import Workspace, WorkspaceDocument, WorkspaceFlag  # noqa: E402
from app.models.workspace_job import WorkspaceJob  # noqa: E402

Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Demo credentials (document these in DEMO.md)
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@inversiq.com"
DEMO_PASSWORD = "Demo2025!"
DEMO_TENANT_ID = "demo-tenant"

TENANT_ID = "demo"          # tenant_id on workspace records — always "demo"
WORKSPACE_NAME = "Basingstoke Logistics Park — Delin Q2 2025"

# ---------------------------------------------------------------------------
# Document extracted data
# ---------------------------------------------------------------------------

DOCS = [
    {
        "filename": "Basingstoke_Park_IM_v3.pdf",
        "doc_type": "information_memorandum",
        "classification_confidence": "0.94",
        "status": "validated",
        "extracted_data": {
            "property_name": "Basingstoke Logistics Park",
            "location": "Basingstoke, Hampshire",
            "asset_type": "Modern Logistics / Distribution",
            "total_gla_sqm": 42500,
            "asking_price_gbp": 52000000,
            "net_initial_yield": "5.8%",
            "erv_psm": 85,
            "wault_years": "6.2",
            "occupancy_rate": "94.1%",
            "capex_budget": None,
            "vendor": "Delin Property",
            "completion_year": 2019,
        },
    },
    {
        "filename": "RentRoll_Q1_2025.xlsx",
        "doc_type": "rent_roll",
        "classification_confidence": "0.91",
        "status": "validated",
        "extracted_data": {
            "total_gla_sqm": 42500,
            "passing_rent_annual_gbp": 2890000,
            "average_erv_psm": 85.3,
            "tenants": [
                {
                    "tenant_name": "Heron Logistics MX Ltd",
                    "sqm": 28500,
                    "passing_rent_annual": 1950000,
                    "lease_start": "2021-03-15",
                    "lease_expiry": "2031-03-15",
                    "break_date": "2027-09-15",
                    "erv_psm": 84.5,
                },
                {
                    "tenant_name": "StoragePro UK Ltd",
                    "sqm": 9200,
                    "passing_rent_annual": 640000,
                    "lease_start": "2022-06-01",
                    "lease_expiry": "2027-06-01",
                    "break_date": None,
                    "erv_psm": 85.0,
                },
                {
                    "tenant_name": "BuildCo Direct",
                    "sqm": 4800,
                    "passing_rent_annual": 300000,
                    "lease_start": "2023-01-01",
                    "lease_expiry": "2026-01-01",
                    "break_date": None,
                    "erv_psm": 87.5,
                },
            ],
        },
    },
    {
        "filename": "TDD_Arcadis_Final_Mar2025.pdf",
        "doc_type": "tdd_report",
        "classification_confidence": "0.88",
        "status": "validated",
        "extracted_data": {
            "inspector": "Arcadis",
            "inspection_date": "2025-03-15",
            "cat1_capex_gbp": 340000,
            "cat2_capex_gbp": 890000,
            "cat1_items": [
                "Roof membrane repairs (Unit A) -- 185,000",
                "M&E controls upgrade -- 95,000",
                "Drainage remediation (loading bay) -- 60,000",
            ],
            "roof_condition": "Fair -- replace within 5 years",
            "epc_rating": "C",
            "structural_condition": "Good",
        },
    },
    {
        "filename": "Cushman_Valuation_Apr2025.pdf",
        "doc_type": "valuation_report",
        "classification_confidence": "0.96",
        "status": "validated",
        "extracted_data": {
            "valuer": "Cushman & Wakefield",
            "valuation_date": "2025-04-01",
            "market_value_gbp": 52500000,
            "erv_psm": 95,
            "cap_rate": "5.5%",
            "equivalent_yield": "5.6%",
            "gross_erv_annual": 4037500,
            "methodology": "Investment method (term and reversion)",
        },
    },
    {
        "filename": "HeronMX_LeaseAgreement_Mar2021.pdf",
        "doc_type": "lease_agreement",
        "classification_confidence": "0.83",
        "status": "validated",
        "extracted_data": {
            "tenant_name": "Heron Logistics MX Ltd",
            "landlord": "Delin Property BV",
            "net_area_sqm": 28500,
            "annual_rent_gbp": 1950000,
            "lease_start": "2021-03-15",
            "lease_expiry": "2031-03-15",
            "break_option_date": "2027-09-15",
            "break_notice_months": 12,
            "rent_review": "5-yearly upward only, linked to RPI cap 4%",
        },
    },
]

# ---------------------------------------------------------------------------
# Workspace-level extracted summary
# ---------------------------------------------------------------------------

EXTRACTED_SUMMARY = {
    "property": "Basingstoke Logistics Park",
    "location": "Basingstoke, Hampshire",
    "asset_type": "Modern Logistics / Distribution",
    "total_gla_sqm": "42,500",
    "asking_price": "52,000,000",
    "passing_rent_pa": "2,890,000",
    "net_initial_yield": "5.8%",
    "wault": "6.2 years",
    "occupancy": "94.1%",
    "valuation_erv_psm": "95",
    "im_erv_psm": "85",
    "cat1_capex": "340,000",
    "cat2_capex": "890,000",
    "epc_rating": "C",
    "valuation_date": "April 2025",
    "valuer": "Cushman & Wakefield",
    "tdd_inspector": "Arcadis",
    "tenants": "3 (Heron MX, StoragePro, BuildCo)",
    "break_option": "Heron -- 15 Sep 2027",
}

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

FLAGS = [
    {
        "flag_type": "erv_deviation",
        "severity": "high",
        "title": "ERV Source Conflict — 11.2% Spread",
        "detail": (
            "The Information Memorandum states an ERV of 85/sqm while the Cushman & Wakefield "
            "Valuation Report (April 2025) independently values the same space at 95/sqm -- "
            "an 11.2% spread. At 42,500 sqm this implies a 4.25m annual rental value gap, "
            "which materially affects yield-on-cost and IRR projections. "
            "The valuation ERV is the more current, independent figure and should be treated "
            "as the underwriting basis unless the vendor can evidence the IM assumption."
        ),
        "conflict_data": {
            "sources": [
                {"doc": "Information Memorandum (v3)", "value": "85 /sqm", "label": "ERV"},
                {"doc": "Cushman & Wakefield Valuation", "value": "95 /sqm", "label": "ERV"},
            ],
            "delta_pct": 11.2,
            "reasoning": (
                "Extracted 'erv_psm' from both IM (page 4, headline assumptions) and valuation "
                "report (page 12, ERV analysis). Deviation of 11.2% exceeds the 10% materiality "
                "threshold. Valuation date is April 2025 vs IM dated November 2024 -- the "
                "valuation reflects more recent comparable evidence from the M3 corridor."
            ),
            "suggested_resolution": (
                "Accept valuation ERV of 95/sqm as underwriting basis. "
                "Request vendor justification for the IM understatement. "
                "Rerun IRR model with corrected ERV -- expected +35-50bps on exit yield."
            ),
        },
    },
    {
        "flag_type": "capex_undisclosed",
        "severity": "high",
        "title": "340k Category 1 Capex Not Disclosed in IM",
        "detail": (
            "The Arcadis Technical Due Diligence Report (March 2025) identifies 340,000 of "
            "Category 1 (immediate) capital expenditure requirements: roof membrane repairs to "
            "Unit A (185k), M&E controls upgrade (95k), and loading bay drainage remediation "
            "(60k). The Information Memorandum contains no capex allowance whatsoever. "
            "This omission overstates the effective acquisition price by approximately 0.65% "
            "and distorts short-term cash flow projections. An additional 890,000 of Category 2 "
            "capex is flagged for 5-year capital planning."
        ),
        "conflict_data": {
            "sources": [
                {"doc": "TDD Report -- Arcadis (Mar 2025)", "value": "340,000 Cat.1 + 890,000 Cat.2", "label": "Capex"},
                {"doc": "Information Memorandum (v3)", "value": "Not disclosed", "label": "Capex"},
            ],
            "cat1_capex_gbp": 340000,
            "cat2_capex_gbp": 890000,
            "reasoning": (
                "TDD report extracted Cat.1 and Cat.2 capex line items from Section 4.2 (Immediate "
                "Works Schedule). IM searched for capex, CAPEX, capital expenditure, works -- no "
                "mention found across 38 pages. Under RICS Red Book guidance, Cat.1 items represent "
                "works required within 12 months to maintain building condition and compliance."
            ),
            "suggested_resolution": (
                "Option A: Deduct 340k from net acquisition price (vendor credit). "
                "Option B: Price-chip by full Cat.1 amount with a 10% contingency (374k). "
                "Provision 890k Cat.2 in 5-year asset management capex plan. "
                "Do not proceed to exclusivity without vendor acknowledgement of TDD findings."
            ),
        },
    },
    {
        "flag_type": "lease_date_validity",
        "severity": "medium",
        "title": "Break Option Date Not Aligned to Quarter Day",
        "detail": (
            "The Heron Logistics MX Ltd lease agreement (March 2021) states a break option "
            "date of 15 September 2027. Commercial lease breaks in England & Wales customarily "
            "fall on a quarter day (25 Mar, 24 Jun, 29 Sep, 25 Dec) or on the first day of a "
            "month for modern institutional leases. A mid-month date of the 15th is non-standard "
            "and may indicate a drafting error or a bespoke notice provision. "
            "Notice period is 12 months -- making the deadline September 2026."
        ),
        "conflict_data": {
            "sources": [
                {"doc": "Heron MX Lease Agreement (2021)", "value": "15 September 2027", "label": "Break date"},
                {"doc": "UK institutional convention", "value": "29 September 2027", "label": "Expected"},
            ],
            "break_notice_months": 12,
            "notice_deadline": "15 September 2026",
            "reasoning": (
                "Extracted break_option_date from lease clause 12.3. Date validated against standard "
                "English quarter days and first-of-month pattern. 15 September is neither. "
                "Notice period is 12 months (clause 12.4), making the notice deadline 15 September 2026 "
                "-- within 18 months of today, requiring urgent calendar flagging."
            ),
            "suggested_resolution": (
                "Instruct solicitors to confirm break date against engrossed lease. "
                "Most likely correct date is 29 September 2027 (Michaelmas quarter day). "
                "Regardless of outcome: calendar notice deadline September 2026. "
                "Obtain tenant confirmation of break intent at next rent quarter."
            ),
        },
    },
]


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed():
    db = SessionLocal()
    ws_id = None
    try:
        # --- Demo tenant ---
        tenant = db.query(Tenant).filter(Tenant.id == DEMO_TENANT_ID).first()
        if tenant:
            print("Reusing existing demo tenant.")
        else:
            tenant = Tenant(
                id=DEMO_TENANT_ID,
                name="Delin Property Demo",
                company_name="Delin Property",
                email=DEMO_EMAIL,
                sector="construction",   # must be a valid registered sector
            )
            db.add(tenant)
            db.flush()
            print("Created demo tenant.")

        # Ensure sector is set (idempotent)
        if not tenant.sector:
            tenant.sector = "construction"
            db.flush()

        # --- Demo user ---
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user:
            # Reset password so credentials are always known
            user.password_hash = hash_password(DEMO_PASSWORD)
            user.tenant_id = DEMO_TENANT_ID
            user.is_active = True
            print("Reset demo user password.")
        else:
            user = User(
                id=uuid.uuid4().hex,
                tenant_id=DEMO_TENANT_ID,
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                is_active=True,
            )
            db.add(user)
            print("Created demo user.")
        db.flush()

        # --- Workspace --- clear ALL demo workspaces to ensure a clean slate
        existing = (
            db.query(Workspace)
            .filter(Workspace.tenant_id == TENANT_ID)
            .all()
        )
        for ws in existing:
            db.query(WorkspaceJob).filter(WorkspaceJob.workspace_id == ws.id).delete()
            db.query(WorkspaceFlag).filter(WorkspaceFlag.workspace_id == ws.id).delete()
            db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == ws.id).delete()
            db.delete(ws)
        if existing:
            print(f"Cleared {len(existing)} existing workspace(s).")

        ws_id = uuid.uuid4().hex
        workspace = Workspace(
            id=ws_id,
            tenant_id=TENANT_ID,
            name=WORKSPACE_NAME,
            vertical_id="cre",
            status="needs_review",
            overall_confidence="0.72",
            extracted_summary=EXTRACTED_SUMMARY,
        )
        db.add(workspace)
        db.flush()

        # --- Documents ---
        doc_ids = []
        for d in DOCS:
            doc = WorkspaceDocument(
                workspace_id=ws_id,
                filename=d["filename"],
                doc_type=d["doc_type"],
                classification_confidence=d["classification_confidence"],
                status=d["status"],
                extracted_data=d["extracted_data"],
            )
            db.add(doc)
            db.flush()
            doc_ids.append(doc.id)

        # --- Flags ---
        flag_doc_pairs = [
            [doc_ids[0], doc_ids[3]],   # ERV: IM vs Valuation
            [doc_ids[0], doc_ids[2]],   # Capex: IM vs TDD
            [doc_ids[1], doc_ids[4]],   # Lease date: RentRoll vs Lease
        ]
        for i, f in enumerate(FLAGS):
            flag = WorkspaceFlag(
                workspace_id=ws_id,
                flag_type=f["flag_type"],
                severity=f["severity"],
                title=f["title"],
                detail=f["detail"],
                source_document_ids=flag_doc_pairs[i],
                conflict_data=f["conflict_data"],
                status="open",
            )
            db.add(flag)

        db.commit()

        print("")
        print("Demo seed complete.")
        print("")
        print("  Login        : " + DEMO_EMAIL)
        print("  Password     : " + DEMO_PASSWORD)
        print("  Workspace ID : " + ws_id)
        print("  Documents    : " + str(len(DOCS)) + " (all validated)")
        print("  Flags        : 3 open (2 HIGH, 1 MEDIUM)")
        print("")
        print("  URL          : http://localhost:3000/workspaces/" + ws_id)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
