from pathlib import Path
from uuid import uuid4
import re
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.services.onboarding_email_service import send_welcome_email_task
from app.services.password_reset_email_service import (
    build_password_reset_url,
    send_password_reset_email,
)
from app.services.password_reset_service import (
    cleanup_expired_password_reset_tokens,
    consume_password_reset_token_atomic,
    create_password_reset_token,
    validate_password_reset_token,
)
from app.i18n.service import setup_jinja_i18n

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "verticals" / "paintly" / "templates"
)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
setup_jinja_i18n(templates)


def slugify(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


async def _send_password_reset_email_task(*, to_email: str, reset_url: str) -> None:
    """
    Background sender for forgot-password requests.
    Keep this best-effort and non-throwing so UI responses stay neutral.
    """
    try:
        result = await send_password_reset_email(
            to_email=to_email,
            reset_url=reset_url,
            expiry_minutes=60,
        )
        if not result.ok:
            logger.warning(
                "AUTH_FORGOT_PASSWORD_EMAIL_NOT_SENT to=%s skipped=%s reason=%s http_status=%s error_code=%s",
                to_email,
                result.skipped,
                result.skip_reason,
                result.http_status,
                result.error_code,
            )
    except Exception:
        logger.exception("AUTH_FORGOT_PASSWORD_EMAIL_TASK_FAILED to=%s", to_email)


# ---------- HTML pages ----------


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/app/leads", reset: int = 0):
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "next": next, "reset": bool(reset)},
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request},
    )


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, sent: int = 0):
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {
            "request": request,
            "sent": bool(sent),
        },
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    token: str = "",
    db: Session = Depends(get_db),
):
    token = (token or "").strip()
    token_valid = False
    if token:
        token_valid = validate_password_reset_token(db=db, raw_token=token) is not None
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {
            "request": request,
            "token": token,
            "token_valid": token_valid,
            "error": None,
        },
    )


# ---------- Form POST endpoints (cookie-setting) ----------


@router.post("/login")
def login_form(
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/app/leads"),
    db: Session = Depends(get_db),
):
    logger.info("AUTH_LOGIN_FORM_HIT email=%s", email)
    email_norm = email.lower().strip()
    user = db.query(User).filter(User.email == email_norm).first()

    if not user or not verify_password(password, user.password_hash):
        logger.warning("AUTH_LOGIN_INVALID_CREDENTIALS email=%s", email_norm)
        return RedirectResponse(url=f"/auth/login?next={next}", status_code=302)

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    if not next.startswith("/"):
        next = "/app/leads"

    logger.info("AUTH_LOGIN_SUCCESS user_id=%s tenant_id=%s", user.id, user.tenant_id)
    resp = RedirectResponse(url=next, status_code=302)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # True in prod
        max_age=60 * 60 * 24,
        path="/",
    )
    return resp


@router.post("/register")
def register_form(
    background_tasks: BackgroundTasks,
    company_name: str | None = Form(default=None),
    email: str = Form(...),
    phone: str | None = Form(default=None),
    walls_rate_eur_per_sqm: float | None = Form(default=None),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    logger.info("AUTH_REGISTER_FORM_HIT email=%s company_name=%s", email, company_name)
    company_name_clean = (company_name or "").strip() or "Mijn schildersbedrijf"
    email_norm = email.lower().strip()
    phone_clean = phone.strip() if phone else None

    existing = db.query(User).filter(User.email == email_norm).first()
    if existing:
        logger.warning("AUTH_REGISTER_EMAIL_EXISTS email=%s", email_norm)
        return RedirectResponse(url="/auth/login", status_code=302)

    base_slug = slugify(company_name_clean) or "tenant"
    slug = base_slug
    counter = 2

    while db.query(Tenant).filter(Tenant.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    trial_start = datetime.now(timezone.utc)
    trial_end = trial_start + timedelta(days=14)

    tenant = Tenant(
        id=str(uuid4()),
        name=company_name_clean,
        company_name=company_name_clean,
        email=email_norm,
        phone=phone_clean,
        slug=slug,
        plan_code="pro_199",
        subscription_status="trialing",
        trial_ends_at=trial_end,
        pricing_json=(
            {"walls_rate_eur_per_sqm": float(walls_rate_eur_per_sqm)}
            if walls_rate_eur_per_sqm is not None
            else {}
        ),
    )

    user = User(
        id=str(uuid4()),
        tenant_id=tenant.id,
        email=email_norm,
        password_hash=hash_password(password[:72]),
        is_active=True,
        is_platform_admin=False,
    )

    db.add(tenant)
    db.add(user)
    db.commit()
    db.refresh(tenant)
    db.refresh(user)

    # Schedule welcome email only after a successful commit + refresh so persisted tenant/user IDs exist.
    background_tasks.add_task(send_welcome_email_task, tenant.id, user.id)

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    resp = RedirectResponse(url="/onboarding/link", status_code=303)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # True in prod
        max_age=60 * 60 * 24,
        path="/",
    )
    logger.info(
        "AUTH_REGISTER_SUCCESS user_id=%s tenant_id=%s", user.id, user.tenant_id
    )
    return resp


@router.post("/forgot-password")
def forgot_password_form(
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Always return a neutral success redirect to prevent account enumeration.
    """
    email_norm = email.lower().strip()
    user = db.query(User).filter(User.email == email_norm).first()

    try:
        cleanup_expired_password_reset_tokens(db)

        if user and user.is_active:
            raw_token, _token_row = create_password_reset_token(db, user=user)
            db.commit()

            reset_url = build_password_reset_url(raw_token=raw_token)
            background_tasks.add_task(
                _send_password_reset_email_task,
                to_email=user.email,
                reset_url=reset_url,
            )
            logger.info("AUTH_FORGOT_PASSWORD_ACCEPTED user_id=%s", user.id)
        else:
            db.commit()
            logger.info("AUTH_FORGOT_PASSWORD_ACCEPTED_NON_EXISTENT_OR_INACTIVE")
    except Exception:
        logger.exception("AUTH_FORGOT_PASSWORD_PROCESS_FAILED")
        db.rollback()

    return RedirectResponse(url="/auth/forgot-password?sent=1", status_code=303)


@router.post("/reset-password")
def reset_password_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    raw_token = (token or "").strip()
    new_password = (password or "").strip()
    user: User | None = None

    if len(new_password) < 8:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {
                "request": request,
                "token": raw_token,
                "token_valid": True,
                "error": "Je wachtwoord moet minimaal 8 tekens bevatten.",
            },
            status_code=400,
        )

    try:
        user_id = consume_password_reset_token_atomic(db=db, raw_token=raw_token)
        if not user_id:
            return templates.TemplateResponse(
                "auth/reset_password.html",
                {
                    "request": request,
                    "token": "",
                    "token_valid": False,
                    "error": "Deze resetlink is ongeldig, verlopen of al gebruikt.",
                },
                status_code=400,
            )

        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not user:
            # Keep the token unconsumed by rolling back this transaction.
            db.rollback()
            return templates.TemplateResponse(
                "auth/reset_password.html",
                {
                    "request": request,
                    "token": "",
                    "token_valid": False,
                    "error": "Deze resetlink is ongeldig, verlopen of al gebruikt.",
                },
                status_code=400,
            )

        user.password_hash = hash_password(new_password[:72])
        db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "AUTH_RESET_PASSWORD_FAILED user_id=%s",
            user.id if user is not None else None,
        )
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {
                "request": request,
                "token": raw_token,
                "token_valid": True,
                "error": "Er ging iets mis. Probeer het opnieuw.",
            },
            status_code=500,
        )

    logger.info("AUTH_RESET_PASSWORD_SUCCESS user_id=%s", user.id)
    return RedirectResponse(url="/auth/login?reset=1", status_code=303)


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/auth/login", status_code=302)
    resp.delete_cookie("access_token", path="/")
    return resp
