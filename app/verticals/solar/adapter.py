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
from app.models.lead import Lead, LeadFile

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
            "submit_url": submit_url or "/intake/solar",
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

        yearly_kwh: float | None = None
        raw_kwh = (form_dict.get("yearly_kwh") or "").strip()
        if raw_kwh:
            try:
                yearly_kwh = float(raw_kwh)
            except ValueError:
                pass
        roof_type = (form_dict.get("roof_type") or "").strip() or None
        desired_installation = (form_dict.get("desired_installation") or "").strip() or None
        address = (form_dict.get("address") or "").strip() or None
        project_description = (form_dict.get("project_description") or "").strip() or None
        photo_keys = form.getlist("photo_keys") if hasattr(form, "getlist") else []
        normalized_photo_keys = [str(v).strip() for v in photo_keys if str(v).strip()]

        intake_payload = {
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "yearly_kwh": yearly_kwh,
            "roof_type": roof_type,
            "desired_installation": desired_installation,
            "address": address,
            "project_description": project_description,
            "object_keys": normalized_photo_keys,
            "vertical": self.vertical_id,
        }

        lead = Lead(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            vertical=self.vertical_id,
            name=name,
            email=email,
            phone=phone,
            notes=project_description,
            status="NEW",
            intake_payload=json.dumps(intake_payload, ensure_ascii=False),
        )

        db.add(lead)
        db.commit()
        db.refresh(lead)

        for key in normalized_photo_keys:
            db.add(
                LeadFile(
                    lead_id=lead.id,
                    s3_key=key,
                    size_bytes=0,
                    content_type="image/*",
                )
            )
        if normalized_photo_keys:
            db.commit()

        logger.info(
            "SOLAR_INTAKE lead_id=%s tenant=%s yearly_kwh=%s roof_type=%s desired_installation=%s",
            lead.id, tenant_id, yearly_kwh, roof_type, desired_installation,
        )

        return IntakeResult(
            lead_id=str(lead.id),
            tenant_id=lead.tenant_id,
            vertical=lead.vertical,
            files=normalized_photo_keys,
        )

    async def upsert_lead_from_form(
        self,
        request: Any,
        db: Session,
        tenant_id: str = "public",
    ) -> IntakeResult:
        form = await request.form()
        form_dict = dict(form)

        tenant_id = (tenant_id or "").strip() or "public"
        raw_lead_id = (form_dict.get("lead_id") or "").strip()
        if not raw_lead_id:
            return await self.create_lead_from_form(request, db, tenant_id=tenant_id)

        lead = (
            db.query(Lead)
            .filter(Lead.id == raw_lead_id)
            .filter(Lead.tenant_id == tenant_id)
            .first()
        )
        if not lead:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Lead not found")

        name = (form_dict.get("name") or "").strip()
        email = (form_dict.get("email") or "").strip()
        phone = (form_dict.get("phone") or "").strip() or None
        yearly_kwh: float | None = None
        raw_kwh = (form_dict.get("yearly_kwh") or "").strip()
        if raw_kwh:
            try:
                yearly_kwh = float(raw_kwh)
            except ValueError:
                pass
        roof_type = (form_dict.get("roof_type") or "").strip() or None
        desired_installation = (form_dict.get("desired_installation") or "").strip() or None
        address = (form_dict.get("address") or "").strip() or None
        project_description = (form_dict.get("project_description") or "").strip() or None
        photo_keys = form.getlist("photo_keys") if hasattr(form, "getlist") else []
        normalized_photo_keys = [str(v).strip() for v in photo_keys if str(v).strip()]

        intake_payload = {
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "yearly_kwh": yearly_kwh,
            "roof_type": roof_type,
            "desired_installation": desired_installation,
            "address": address,
            "project_description": project_description,
            "object_keys": normalized_photo_keys,
            "vertical": self.vertical_id,
        }

        lead.name = name
        lead.email = email
        lead.phone = phone
        lead.notes = project_description
        lead.vertical = self.vertical_id
        lead.intake_payload = json.dumps(intake_payload, ensure_ascii=False)
        db.add(lead)
        db.commit()
        db.refresh(lead)

        existing = db.query(LeadFile).filter(LeadFile.lead_id == lead.id).all()
        existing_keys = {lf.s3_key for lf in existing if isinstance(lf.s3_key, str)}
        for key in normalized_photo_keys:
            if key not in existing_keys:
                db.add(
                    LeadFile(
                        lead_id=lead.id,
                        s3_key=key,
                        size_bytes=0,
                        content_type="image/*",
                    )
                )
        db.commit()

        return IntakeResult(
            lead_id=str(lead.id),
            tenant_id=lead.tenant_id,
            vertical=lead.vertical,
            files=normalized_photo_keys,
        )


# Protocol conformance check at import time
_: VerticalAdapter = SolarAdapter()  # type: ignore[assignment]
