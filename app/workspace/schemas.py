"""
app/workspace/schemas.py

Extraction schemas per document type.

Each schema is a dict that:
  - drives the LLM prompt (fields to extract + descriptions)
  - defines validation rules for the validate step
  - declares which fields participate in cross-document checks

Generic: the doc_type taxonomy is vertical-configurable.
The cross-document checks are defined separately in cross_checks.py.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Document type taxonomy
# ---------------------------------------------------------------------------

DOCUMENT_TYPES = {
    "information_memorandum": "Information Memorandum (IM) — marketing document describing the asset for sale",
    "rent_roll": "Rent Roll — schedule of current tenants, areas, rents and lease terms",
    "tdd_report": "Technical Due Diligence (TDD) report — structural and physical condition assessment",
    "valuation_report": "Valuation / Appraisal report — independent market value and ERV assessment",
    "lease_agreement": "Lease Agreement or Heads of Terms — legal contract between landlord and tenant",
    "loan_termsheet": "Loan Term Sheet or Financing Proposal — bank financing terms",
    "financial_statements": "Financial Statements — P&L, balance sheet, or management accounts",
    "epc_certificate": "Energy Performance Certificate (EPC) — energy efficiency rating",
    "site_plan": "Site Plan or Floor Plan — architectural drawings",
    "other": "Other — document does not match any known type",
}

# ---------------------------------------------------------------------------
# Extraction field schemas per document type
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "information_memorandum": {
        "fields": {
            "asset_name": "Name of the property or asset",
            "location": "Address or city/region of the asset",
            "asset_type": "Type of asset (e.g. logistics, warehouse, office, retail, mixed)",
            "total_gla_sqm": "Total Gross Leasable Area in square metres (number only)",
            "asking_price": "Asking price or guide price (number, in local currency)",
            "currency": "Currency of the asking price (e.g. GBP, EUR)",
            "gross_initial_yield_pct": "Gross Initial Yield as a percentage (number only, e.g. 5.5 for 5.5%)",
            "net_initial_yield_pct": "Net Initial Yield as a percentage",
            "passing_rent_annual": "Total passing / contracted rent per year (number)",
            "erv_psm": "Estimated Rental Value per square metre per year (number)",
            "capex_budget": "Any capex budget or refurbishment cost mentioned (number, or null if absent)",
            "number_of_tenants": "Number of tenants currently in occupation (integer)",
            "occupancy_pct": "Current occupancy rate as a percentage (number only)",
            "vendor_name": "Name of the vendor or seller if mentioned",
        },
        "required": ["asset_name", "total_gla_sqm", "asking_price"],
    },
    "rent_roll": {
        "fields": {
            "total_gla_sqm": "Total Gross Leasable Area across all tenants in square metres",
            "total_passing_rent_annual": "Sum of all passing rents per year",
            "currency": "Currency used in the rent roll",
            "average_erv_psm": "Average Estimated Rental Value per sqm per year across all units",
            "number_of_tenants": "Total number of tenant lines (including vacant units)",
            "vacancy_sqm": "Total vacant area in square metres",
            "tenants": (
                "Array of tenant objects. Each object must have: "
                "tenant_name (string), sqm (number), passing_rent_annual (number), "
                "lease_start (YYYY-MM-DD or null), lease_expiry (YYYY-MM-DD or null), "
                "break_date (YYYY-MM-DD or null), erv_psm (number or null)"
            ),
        },
        "required": ["total_gla_sqm", "tenants"],
    },
    "tdd_report": {
        "fields": {
            "asset_name": "Name of the inspected property",
            "inspection_date": "Date of inspection (YYYY-MM-DD)",
            "author_firm": "Name of the firm that produced the report",
            "epc_rating": "EPC rating if mentioned (e.g. A, B, C, D, E)",
            "category_1_capex": "Immediate / Category 1 capex required (number, local currency, or null)",
            "category_2_capex": "Short-term / Category 2 capex required (number, or null)",
            "total_capex": "Total recommended capex across all categories (number, or null)",
            "currency": "Currency of capex figures",
            "major_issues": "List of significant issues identified (array of strings, max 10)",
            "structural_condition": "Overall structural condition summary (one sentence)",
        },
        "required": ["category_1_capex"],
    },
    "valuation_report": {
        "fields": {
            "asset_name": "Name of the valued property",
            "valuation_date": "Date of the valuation (YYYY-MM-DD)",
            "valuer_firm": "Name of the valuation firm",
            "market_value": "Assessed market value (number, local currency)",
            "currency": "Currency of the valuation",
            "net_initial_yield_pct": "Assessed net initial yield as percentage",
            "reversionary_yield_pct": "Assessed reversionary yield as percentage",
            "erv_psm_warehouse": "ERV per sqm per year for warehouse / industrial space (number or null)",
            "erv_psm_office": "ERV per sqm per year for office space (number or null)",
            "erv_psm_other": "ERV per sqm per year for other space types (number or null)",
            "void_assumption_months": "Assumed void period in months (number or null)",
            "rent_free_assumption_months": "Assumed rent-free incentive in months (number or null)",
            "erv_growth_pct_annual": "Assumed annual ERV growth rate as percentage (number or null)",
        },
        "required": ["market_value", "erv_psm_warehouse"],
    },
    "lease_agreement": {
        "fields": {
            "tenant_name": "Name of the tenant",
            "property_address": "Address of the leased premises",
            "demised_area_sqm": "Area of the demised premises in square metres",
            "lease_start_date": "Lease start date (YYYY-MM-DD)",
            "lease_expiry_date": "Lease expiry / end date (YYYY-MM-DD)",
            "break_date": "Tenant break option date (YYYY-MM-DD or null)",
            "break_conditions": "Summary of break conditions (string or null)",
            "passing_rent_annual": "Annual rent at lease commencement (number)",
            "currency": "Currency",
            "rent_review_mechanism": "Rent review basis (e.g. CPI, open market, fixed uplift)",
            "rent_free_months": "Rent-free period in months (number or null)",
            "deposit_amount": "Deposit or rent bond amount (number or null)",
        },
        "required": ["tenant_name", "lease_start_date", "lease_expiry_date", "passing_rent_annual"],
    },
    "loan_termsheet": {
        "fields": {
            "lender_name": "Name of the lending institution",
            "loan_amount": "Facility amount (number)",
            "currency": "Currency",
            "ltv_pct": "Loan to Value ratio as percentage",
            "interest_rate_basis": "Interest rate basis (e.g. EURIBOR + 175bps, fixed 4.5%)",
            "margin_bps": "Bank margin in basis points (integer or null)",
            "arrangement_fee_pct": "Arrangement fee as percentage of loan (number or null)",
            "term_years": "Loan term in years (number)",
            "drawdown_date": "Expected drawdown date (YYYY-MM-DD or null)",
            "amortisation_pct_annual": "Annual amortisation as percentage (number or null, 0 if interest-only)",
        },
        "required": ["loan_amount", "ltv_pct"],
    },
    "other": {
        "fields": {
            "document_summary": "Brief one-paragraph summary of the document's content",
            "key_figures": "List of any significant numerical figures mentioned (array of strings)",
        },
        "required": [],
    },
}


def get_schema(doc_type: str) -> dict[str, Any]:
    return EXTRACTION_SCHEMAS.get(doc_type, EXTRACTION_SCHEMAS["other"])
