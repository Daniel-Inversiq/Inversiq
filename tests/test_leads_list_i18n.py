from __future__ import annotations

from pathlib import Path

from app.i18n.service import translate


def test_leads_list_catalog_supports_english_labels() -> None:
    assert translate("leads_list.header.title", lang="en") == "Today to arrange"
    assert translate("leads_list.table.customer", lang="en") == "Customer"
    assert translate("leads_list.empty.no_results_title", lang="en") == "No quotes found"


def test_leads_list_catalog_has_dutch_defaults() -> None:
    assert translate("leads_list.header.title", lang="nl") == "Vandaag te regelen"
    assert translate("leads_list.stats.overdue_followup", lang="nl") == "Te laat voor follow-up"


def test_leads_list_templates_use_i18n_helper() -> None:
    root = Path(__file__).resolve().parents[1]
    page_template = (
        root / "app" / "verticals" / "construction" / "templates" / "app" / "leads_list.html"
    ).read_text(encoding="utf-8")
    table_template = (
        root
        / "app"
        / "verticals"
        / "construction"
        / "templates"
        / "leads"
        / "partials"
        / "table_body.html"
    ).read_text(encoding="utf-8")

    assert "t('leads_list.header.title')" in page_template
    assert "t('leads_list.table.customer')" in page_template
    assert "t('leads_list.empty.no_results_title')" in table_template
