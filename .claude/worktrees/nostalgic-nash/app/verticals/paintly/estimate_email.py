from __future__ import annotations

import logging
from typing import Optional

from app.services.email_service import send_email, EmailSendError
from app.verticals.paintly.email_render import render_estimate_ready_email

logger = logging.getLogger(__name__)


async def send_estimate_ready_email_to_customer(
    *,
    to_email: str,
    customer_name: str,
    quote_url: str,
    company_name: str,
    lead_id: Optional[int] = None,
    tenant_id: Optional[str] = None,
) -> None:
    """
    Shared helper to send the customer 'estimate ready' email.
    Expects that quote_url already includes the public /e/{token} link.
    """
    html_body = render_estimate_ready_email(
        customer_name=customer_name,
        quote_url=quote_url,
        company_name=company_name,
    )

    text_body = (
        f"Beste {customer_name or 'klant'},\n\n"
        "Uw offerte staat klaar. U kunt deze vrijblijvend online bekijken, met duidelijke prijsopbouw, en eenvoudig accepteren of afwijzen.\n\n"
        f"Bekijk uw offerte: {quote_url}\n"
    )

    metadata: dict[str, str] = {}
    if lead_id is not None:
        metadata["lead_id"] = str(lead_id)
    if tenant_id is not None:
        metadata["tenant_id"] = str(tenant_id)

    logger.info(
        "ESTIMATE_READY_PROVIDER_SEND_START lead_id=%s tenant_id=%s to=%s quote_url=%s",
        str(lead_id) if lead_id is not None else "",
        str(tenant_id) if tenant_id is not None else "",
        to_email,
        quote_url,
    )
    try:
        await send_email(
            to=to_email,
            subject="Uw offerte staat klaar",
            html_body=html_body,
            text_body=text_body,
            tag="customer-estimate-ready",
            metadata=metadata,
        )
        logger.info(
            "ESTIMATE_READY_PROVIDER_SUCCESS lead_id=%s tenant_id=%s to=%s",
            str(lead_id) if lead_id is not None else "",
            str(tenant_id) if tenant_id is not None else "",
            to_email,
        )
    except EmailSendError as exc:
        logger.exception(
            "ESTIMATE_READY_PROVIDER_FAILURE lead_id=%s tenant_id=%s to=%s error=%s",
            str(lead_id) if lead_id is not None else "",
            str(tenant_id) if tenant_id is not None else "",
            to_email,
            str(exc),
        )
        raise

