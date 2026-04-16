from celery import current_task
import structlog
from app.celery_app import celery_app, update_job_status, logger
from app.services.predictor import SimplePredictor
from app.services.quote_renderer import QuoteRenderer
from app.services.pricing_engine import PricingEngine
from app.services.hubspot_client import HubSpotClient
from app.services.tenant_service import TenantService
from app.models.tenant_settings import TenantSettings
from app.metrics import record_job_metrics
from app.logging_config import set_context
from app.infra.retry import retry_on_transient
from app.infra.errors import classify_exception, is_terminal
from typing import Dict, Any, List
import traceback
import time

_slog = structlog.get_logger("aether.tasks")

# Initialiseer services
predictor = SimplePredictor()
quote_renderer = QuoteRenderer()
pricing_engine = PricingEngine()
hubspot_client = HubSpotClient()
tenant_service = TenantService()

@celery_app.task(bind=True, name="vision_predict")
def vision_predict_task(self, job_id: str, lead_id: str, image_paths: List[str], m2: float, tenant_id: str, lead_data: Dict[str, Any] = None):
    """Vision prediction taak"""
    start_time = time.time()
    log = _slog.bind(task="vision_predict", job_id=job_id, lead_id=lead_id, tenant_id=tenant_id)

    # Set loguru context for file-based handlers
    set_context(tenant_id=tenant_id, lead_id=lead_id)

    try:
        log.info("task_start")
        update_job_status(job_id, "processing", {"step": "vision_predict"})

        # Voer predictie uit — wrap in retry for transient/network failures
        prediction = retry_on_transient(
            lambda: predictor.predict(lead_id=lead_id, image_paths=image_paths, m2=m2),
            attempts=3,
            base=0.5,
            cap=5.0,
        )

        duration = time.time() - start_time
        record_job_metrics("vision_predict", tenant_id, "completed", duration)

        log.info("task_completed", duration_s=round(duration, 3))
        update_job_status(job_id, "completed", {
            "step": "vision_predict",
            "prediction": prediction
        })

        # Start volgende stap: compute_price
        if lead_data:
            compute_price_task.delay(
                job_id=job_id,
                m2=m2,
                substrate=prediction.get("substrate", "bestaand"),
                issues=prediction.get("issues", []),
                lead_data=lead_data,
                tenant_id=tenant_id
            )
            log.info("task_enqueued", next_task="compute_price")

        return prediction

    except Exception as e:
        duration = time.time() - start_time
        record_job_metrics("vision_predict", tenant_id, "failed", duration)

        category = classify_exception(e)
        error_category = category.value
        terminal = is_terminal(e)
        log.error(
            "task_failed",
            error_category=error_category,
            terminal=terminal,
            exc=f"{type(e).__name__}: {e}",
            duration_s=round(duration, 3),
        )
        update_job_status(job_id, "failed", error=str(e), result={"error_category": error_category})
        raise

@celery_app.task(bind=True, name="generate_pdf")
def generate_pdf_task(self, job_id: str, lead_data: Dict[str, Any], prediction: Dict[str, Any],
                     pricing_result: Dict[str, Any], tenant_id: str):
    """PDF generatie taak"""
    log = _slog.bind(task="generate_pdf", job_id=job_id, tenant_id=tenant_id)
    try:
        log.info("task_start")
        update_job_status(job_id, "processing", {"step": "generate_pdf"})

        # Haal tenant settings op
        tenant_settings = tenant_service.get_tenant(tenant_id)
        if not tenant_settings:
            raise Exception(f"Tenant {tenant_id} not found")

        # Genereer offerte — S3 write is idempotent, safe to retry on transient failure
        quote_result = retry_on_transient(
            lambda: quote_renderer.render_quote(
                lead=lead_data,
                prediction=prediction,
                pricing=pricing_result,
                tenant_settings=tenant_settings,
            ),
            attempts=3,
            base=0.5,
            cap=5.0,
        )

        log.info("task_completed")
        update_job_status(job_id, "completed", {
            "step": "generate_pdf",
            "quote_result": quote_result
        })

        # Start laatste stap: crm_push
        crm_push_task.delay(
            job_id=job_id,
            lead_data=lead_data,
            quote_result=quote_result,
            pricing_result=pricing_result,
            tenant_id=tenant_id
        )
        log.info("task_enqueued", next_task="crm_push")

        return quote_result

    except Exception as e:
        category = classify_exception(e)
        error_category = category.value
        terminal = is_terminal(e)
        log.error(
            "task_failed",
            error_category=error_category,
            terminal=terminal,
            exc=f"{type(e).__name__}: {e}",
        )
        update_job_status(job_id, "failed", error=str(e), result={"error_category": error_category})
        raise

@celery_app.task(bind=True, name="crm_push")
def crm_push_task(self, job_id: str, lead_data: Dict[str, Any], quote_result: Dict[str, Any],
                 pricing_result: Dict[str, Any], tenant_id: str):
    """CRM push taak"""
    log = _slog.bind(task="crm_push", job_id=job_id, tenant_id=tenant_id)
    try:
        log.info("task_start")
        update_job_status(job_id, "processing", {"step": "crm_push"})

        # Haal tenant settings op
        tenant_settings = tenant_service.get_tenant(tenant_id)
        if not tenant_settings or not tenant_settings.hubspot_token:
            log.info("crm_push_skipped", reason="hubspot_not_configured")
            update_job_status(job_id, "completed", {
                "step": "crm_push",
                "message": "HubSpot not configured"
            })
            return {"message": "HubSpot not configured"}

        # Configureer HubSpot client
        hubspot_client.set_token(tenant_settings.hubspot_token)

        # Push naar HubSpot CRM
        contact_id = hubspot_client.upsert_contact(
            email=lead_data["email"],
            name=lead_data["name"],
            phone=lead_data.get("phone", "")
        )

        if contact_id:
            deal_id = hubspot_client.create_deal(
                amount=pricing_result["total"],
                name=f"Offerte {quote_result['quote_id']} - {lead_data['name']}"
            )

            if deal_id:
                # Koppel contact aan deal
                hubspot_client.associate_contact_with_deal(contact_id, deal_id)

                # Voeg note toe met offerte URL
                hubspot_client.attach_note(deal_id, quote_result["html_url"])

                log.info("task_completed", contact_id=contact_id, deal_id=deal_id)
                update_job_status(job_id, "completed", {
                    "step": "crm_push",
                    "contact_id": contact_id,
                    "deal_id": deal_id
                })
                return {"contact_id": contact_id, "deal_id": deal_id}
            else:
                raise Exception("Failed to create deal in HubSpot")
        else:
            raise Exception("Failed to create contact in HubSpot")

    except Exception as e:
        category = classify_exception(e)
        error_category = category.value
        terminal = is_terminal(e)
        # CRM push is not retried here — HubSpot create_deal is not idempotent.
        # The category is logged for alerting/observability.
        log.error(
            "task_failed",
            error_category=error_category,
            terminal=terminal,
            exc=f"{type(e).__name__}: {e}",
        )
        update_job_status(job_id, "failed", error=str(e), result={"error_category": error_category})
        raise

@celery_app.task(bind=True, name="compute_price")
def compute_price_task(self, job_id: str, m2: float, substrate: str, issues: List[str], lead_data: Dict[str, Any] = None, tenant_id: str = None):
    """Prijsberekening taak"""
    log = _slog.bind(task="compute_price", job_id=job_id, tenant_id=tenant_id)
    try:
        log.info("task_start")
        update_job_status(job_id, "processing", {"step": "compute_price"})

        # Bereken prijs
        pricing_result = pricing_engine.compute_price(
            m2=m2,
            substrate=substrate,
            issues=issues
        )

        log.info("task_completed")
        update_job_status(job_id, "completed", {
            "step": "compute_price",
            "pricing_result": pricing_result
        })

        # Start volgende stap: generate_pdf
        if lead_data and tenant_id:
            generate_pdf_task.delay(
                job_id=job_id,
                lead_data=lead_data,
                prediction={"substrate": substrate, "issues": issues},
                pricing_result=pricing_result,
                tenant_id=tenant_id
            )
            log.info("task_enqueued", next_task="generate_pdf")

        return pricing_result

    except Exception as e:
        category = classify_exception(e)
        error_category = category.value
        terminal = is_terminal(e)
        log.error(
            "task_failed",
            error_category=error_category,
            terminal=terminal,
            exc=f"{type(e).__name__}: {e}",
        )
        update_job_status(job_id, "failed", error=str(e), result={"error_category": error_category})
        raise
