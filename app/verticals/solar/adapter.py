# app/verticals/solar/adapter.py
"""
SolarAdapter — wires the solar vertical into the shared intake/app shell.

render_intake_form(): stub — not yet wired to a route.
create_lead_from_form(): real — parses form data and creates a Lead row.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from fastapi.templating import Jinja2Templates

from app.core.contracts import IntakeResult, VerticalAdapter
from app.models.lead import Lead

logger = logging.getLogger(__name__)

_templates = Jinja2Templates(directory="app/verticals/solar/templates")


class SolarAdapter:
    vertical_id: str = "solar"

    def render_intake_form(
        self,
        request: Any,
        lead_id: str,
        tenant_id: str = "public",
        extra_context: dict | None = None,
        submit_url: str | None = None,
    ) -> Any:
        context: dict = {
            "request": request,
            "lead_id": lead_id,
            "tenant_id": tenant_id,
            "vertical": self.vertical_id,
        }
        if extra_context:
            context.update(extra_context)
        return _templates.TemplateResponse("intake_form_solar.html", context)

    async def create_lead_from_form(
        self,
        request: Any,
        db: Session,
        tenant_id: str = "public",
    ) -> IntakeResult:
        form = await request.form()
        form_dict = dict(form)

        tenant_id = (tenant_id or "").strip() or "public"

        name = (form_dict.get("name") or "").strip()
        email = (form_dict.get("email") or "").strip()
        phone = (form_dict.get("phone") or "").strip() or None

        if not name or not email:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="name and email are required")

        system_kw: float | None = None
        raw_kw = (form_dict.get("system_kw") or "").strip()
        if raw_kw:
            try:
                system_kw = float(raw_kw)
            except ValueError:
                pass

        intake_payload = {
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "system_kw": system_kw,   # None → engine falls back to default; triggers needs_review
            "vertical": self.vertical_id,
        }

        lead = Lead(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            vertical=self.vertical_id,
            name=name,
            email=email,
            phone=phone,
            status="NEW",
            intake_payload=json.dumps(intake_payload, ensure_ascii=False),
        )

        db.add(lead)
        db.commit()
        db.refresh(lead)

        logger.info(
            "SOLAR_INTAKE lead_id=%s tenant=%s system_kw=%s",
            lead.id, tenant_id, system_kw,
        )

        return IntakeResult(
            lead_id=str(lead.id),
            tenant_id=lead.tenant_id,
            vertical=lead.vertical,
            files=[],
        )


# Protocol conformance check at import time
_: VerticalAdapter = SolarAdapter()  # type: ignore[assignment]
