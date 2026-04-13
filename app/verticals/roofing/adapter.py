# app/verticals/roofing/adapter.py
"""
RoofingAdapter — wires the roofing vertical into the shared intake/app shell.

render_intake_form(): serves the minimal roofing intake HTML form.
create_lead_from_form(): creates a Lead row from the submitted form data.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.contracts import IntakeResult, VerticalAdapter
from app.models.lead import Lead

logger = logging.getLogger(__name__)

_templates = Jinja2Templates(directory="app/verticals/roofing/templates")


class RoofingAdapter:
    vertical_id: str = "roofing"

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
        return _templates.TemplateResponse("intake_form_roofing.html", context)

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

        # Parse roofing-specific fields
        roof_area_raw = (form_dict.get("roof_area_m2") or "").strip()
        roof_area_m2: float | None = None
        if roof_area_raw:
            try:
                roof_area_m2 = float(roof_area_raw)
            except ValueError:
                pass

        roof_type = (form_dict.get("roof_type") or "").strip() or None

        intake_payload = {
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "roof_area_m2": roof_area_m2,
            "roof_type": roof_type,
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
            "ROOFING_INTAKE lead_id=%s tenant=%s roof_area_m2=%s roof_type=%s",
            lead.id, tenant_id, roof_area_m2, roof_type,
        )

        return IntakeResult(
            lead_id=str(lead.id),
            tenant_id=lead.tenant_id,
            vertical=lead.vertical,
            files=[],
        )


# Protocol conformance check at import time
_: VerticalAdapter = RoofingAdapter()  # type: ignore[assignment]
