"""
app/workspace/cross_checks.py

Cross-document consistency checks.

Each check is a pure function:
  (documents: list[WorkspaceDocument]) -> list[FlagSpec]

FlagSpec is a dict with the same shape as WorkspaceFlag columns.
No DB access — the caller persists the resulting flags.

Adding a new check: write a function matching the signature and append it
to CHECKS. No other wiring required.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

# ---------------------------------------------------------------------------
# FlagSpec — mirrors WorkspaceFlag columns (caller maps to model)
# ---------------------------------------------------------------------------

def _flag(
    flag_type: str,
    severity: str,
    title: str,
    detail: str,
    source_doc_ids: list[int],
    conflict_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "flag_type": flag_type,
        "severity": severity,
        "title": title,
        "detail": detail,
        "source_document_ids": source_doc_ids,
        "conflict_data": conflict_data or {},
    }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_erv_deviation(documents: list[dict]) -> list[dict]:
    """
    Flag when ERV from a rent roll and a valuation report diverge by more
    than 10%. This is one of the most common due diligence surprises.
    """
    flags = []
    rent_rolls = [d for d in documents if d["doc_type"] == "rent_roll" and d.get("extracted_data")]
    valuations = [d for d in documents if d["doc_type"] == "valuation_report" and d.get("extracted_data")]

    for rr in rent_rolls:
        rr_erv = rr["extracted_data"].get("fields", {}).get("average_erv_psm")
        for val in valuations:
            val_erv = val["extracted_data"].get("fields", {}).get("erv_psm_warehouse")
            if rr_erv and val_erv:
                try:
                    rr_val = float(rr_erv)
                    v_val = float(val_erv)
                    if rr_val == 0:
                        continue
                    delta_pct = abs(v_val - rr_val) / rr_val
                    if delta_pct >= 0.10:
                        direction = "above" if v_val > rr_val else "below"
                        flags.append(_flag(
                            flag_type="erv_deviation",
                            severity="high",
                            title="ERV Source Conflict",
                            detail=(
                                f"Valuation ERV (£{v_val:,.0f}/psm) is {delta_pct:.0%} {direction} "
                                f"the Rent Roll average ERV (£{rr_val:,.0f}/psm). "
                                f"Resolve before using ERV in the underwriting model."
                            ),
                            source_doc_ids=[rr["id"], val["id"]],
                            conflict_data={
                                "field": "erv_psm",
                                "sources": [
                                    {"doc": rr["filename"], "doc_type": "rent_roll", "value": rr_val},
                                    {"doc": val["filename"], "doc_type": "valuation_report", "value": v_val},
                                ],
                                "delta_pct": round(delta_pct, 4),
                            },
                        ))
                except (TypeError, ValueError):
                    pass
    return flags


def check_capex_undisclosed(documents: list[dict]) -> list[dict]:
    """
    Flag when TDD identifies Category 1 capex that is absent from the IM budget.
    """
    flags = []
    tdds = [d for d in documents if d["doc_type"] == "tdd_report" and d.get("extracted_data")]
    ims = [d for d in documents if d["doc_type"] == "information_memorandum" and d.get("extracted_data")]

    for tdd in tdds:
        cat1 = tdd["extracted_data"].get("fields", {}).get("category_1_capex")
        if not cat1:
            continue
        try:
            cat1_val = float(cat1)
        except (TypeError, ValueError):
            continue
        if cat1_val <= 0:
            continue

        for im in ims:
            im_capex = im["extracted_data"].get("fields", {}).get("capex_budget")
            im_capex_val = None
            try:
                im_capex_val = float(im_capex) if im_capex else None
            except (TypeError, ValueError):
                pass

            if im_capex_val is None or im_capex_val == 0:
                flags.append(_flag(
                    flag_type="capex_undisclosed",
                    severity="high",
                    title="TDD Capex Not Reflected in IM",
                    detail=(
                        f"The TDD report identifies Category 1 (immediate) capex of "
                        f"£{cat1_val:,.0f}, but the Information Memorandum does not include "
                        f"a capex budget. Verify with the vendor's advisor and adjust the "
                        f"acquisition cost accordingly."
                    ),
                    source_doc_ids=[tdd["id"]] + [im["id"] for im in ims],
                    conflict_data={
                        "field": "capex_budget",
                        "sources": [
                            {"doc": tdd["filename"], "doc_type": "tdd_report", "value": cat1_val, "label": "Cat 1 capex"},
                            {"doc": im["filename"], "doc_type": "information_memorandum", "value": im_capex_val, "label": "IM capex budget"},
                        ],
                    },
                ))
    return flags


def check_lease_date_validity(documents: list[dict]) -> list[dict]:
    """
    Flag lease dates (break, expiry) that do not fall on the first of the month.
    The underwriting model explicitly requires first-of-month dates.
    """
    flags = []
    date_fields = ["lease_expiry", "break_date", "lease_start"]

    for doc in documents:
        if doc["doc_type"] not in ("rent_roll", "lease_agreement"):
            continue
        if not doc.get("extracted_data"):
            continue

        fields = doc["extracted_data"].get("fields", {})

        if doc["doc_type"] == "rent_roll":
            tenants = fields.get("tenants", []) or []
            for tenant in tenants:
                for field in date_fields:
                    raw = tenant.get(field)
                    if not raw:
                        continue
                    try:
                        d = date.fromisoformat(str(raw)[:10])
                        if d.day != 1:
                            flags.append(_flag(
                                flag_type="lease_date_invalid",
                                severity="medium",
                                title="Lease Date Not First of Month",
                                detail=(
                                    f"Tenant '{tenant.get('tenant_name', 'Unknown')}': "
                                    f"{field.replace('_', ' ').title()} is {raw} "
                                    f"(day {d.day}). The underwriting model requires "
                                    f"all lease dates to fall on the first of the month. "
                                    f"Likely correct date: {d.replace(day=1).isoformat()}."
                                ),
                                source_doc_ids=[doc["id"]],
                                conflict_data={
                                    "field": field,
                                    "tenant": tenant.get("tenant_name"),
                                    "raw_value": raw,
                                    "suggested": d.replace(day=1).isoformat(),
                                },
                            ))
                    except (ValueError, TypeError):
                        pass

        elif doc["doc_type"] == "lease_agreement":
            for field in ["lease_start_date", "lease_expiry_date", "break_date"]:
                raw = fields.get(field)
                if not raw:
                    continue
                try:
                    d = date.fromisoformat(str(raw)[:10])
                    if d.day != 1:
                        flags.append(_flag(
                            flag_type="lease_date_invalid",
                            severity="medium",
                            title="Lease Date Not First of Month",
                            detail=(
                                f"{field.replace('_', ' ').title()} is {raw} "
                                f"(day {d.day}). The underwriting model requires "
                                f"all lease dates to fall on the first of the month. "
                                f"Likely correct date: {d.replace(day=1).isoformat()}."
                            ),
                            source_doc_ids=[doc["id"]],
                            conflict_data={
                                "field": field,
                                "raw_value": raw,
                                "suggested": d.replace(day=1).isoformat(),
                            },
                        ))
                except (ValueError, TypeError):
                    pass

    return flags


def check_gla_consistency(documents: list[dict]) -> list[dict]:
    """
    Flag when total GLA from the rent roll and the IM differ by more than 5%.
    """
    flags = []
    rent_rolls = [d for d in documents if d["doc_type"] == "rent_roll" and d.get("extracted_data")]
    ims = [d for d in documents if d["doc_type"] == "information_memorandum" and d.get("extracted_data")]

    for rr in rent_rolls:
        rr_gla = rr["extracted_data"].get("fields", {}).get("total_gla_sqm")
        for im in ims:
            im_gla = im["extracted_data"].get("fields", {}).get("total_gla_sqm")
            if rr_gla and im_gla:
                try:
                    rr_val = float(rr_gla)
                    im_val = float(im_gla)
                    if rr_val == 0:
                        continue
                    delta_pct = abs(im_val - rr_val) / rr_val
                    if delta_pct >= 0.05:
                        flags.append(_flag(
                            flag_type="gla_inconsistency",
                            severity="high",
                            title="GLA Mismatch Between IM and Rent Roll",
                            detail=(
                                f"IM states total GLA of {im_val:,.0f} sqm, but the Rent Roll "
                                f"sums to {rr_val:,.0f} sqm — a {delta_pct:.1%} discrepancy. "
                                f"Verify measured areas with the TDD report."
                            ),
                            source_doc_ids=[rr["id"], im["id"]],
                            conflict_data={
                                "field": "total_gla_sqm",
                                "sources": [
                                    {"doc": rr["filename"], "doc_type": "rent_roll", "value": rr_val},
                                    {"doc": im["filename"], "doc_type": "information_memorandum", "value": im_val},
                                ],
                                "delta_pct": round(delta_pct, 4),
                            },
                        ))
                except (TypeError, ValueError):
                    pass
    return flags


def check_missing_key_documents(documents: list[dict]) -> list[dict]:
    """
    Flag when expected document types for a CRE acquisition are absent.
    """
    present_types = {d["doc_type"] for d in documents if d.get("doc_type")}
    expected = {
        "information_memorandum": "Information Memorandum",
        "rent_roll": "Rent Roll",
        "valuation_report": "Valuation Report",
        "tdd_report": "Technical Due Diligence Report",
    }
    flags = []
    for doc_type, label in expected.items():
        if doc_type not in present_types:
            flags.append(_flag(
                flag_type="missing_document",
                severity="medium",
                title=f"Missing Document: {label}",
                detail=(
                    f"No {label} has been uploaded for this workspace. "
                    f"This document is typically required before underwriting can proceed. "
                    f"Upload the document to enable full cross-document validation."
                ),
                source_doc_ids=[],
            ))
    return flags


# ---------------------------------------------------------------------------
# Registry — order matters: higher-severity checks first
# ---------------------------------------------------------------------------

CHECKS = [
    check_erv_deviation,
    check_capex_undisclosed,
    check_gla_consistency,
    check_lease_date_validity,
    check_missing_key_documents,
]


def run_all_checks(documents: list[dict]) -> list[dict]:
    """Run all registered checks and return a flat list of FlagSpecs."""
    flags = []
    for check_fn in CHECKS:
        try:
            flags.extend(check_fn(documents))
        except Exception:
            pass  # individual check failures never block the pipeline
    return flags
