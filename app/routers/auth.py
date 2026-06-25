from pathlib import Path
from uuid import uuid4
import re
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.core.settings import settings
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
public_router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "verticals" / "construction" / "templates"
)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
setup_jinja_i18n(templates)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str
    next: str | None = "/app/leads"


class RegisterPayload(BaseModel):
    company_name: str | None = None
    email: EmailStr
    phone: str | None = None
    walls_rate_eur_per_sqm: float | None = None
    password: str


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    token: str
    new_password: str


def _is_json_request(request: Request) -> bool:
    content_type = (request.headers.get("content-type") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in content_type or (
        "application/json" in accept and "text/html" not in accept
    )


def _cookie_secure() -> bool:
    env = (getattr(settings, "APP_ENV", "") or getattr(settings, "ENV", "")).lower()
    return env not in {"dev", "development", "local"}


def _set_auth_cookie(response: RedirectResponse | JSONResponse, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=60 * 60 * 24,
        path="/",
    )


def _frontend_base_url() -> str:
    return (
        (settings.APP_SHELL_PUBLIC_BASE_URL or settings.APP_PUBLIC_BASE_URL or "")
        .strip()
        .rstrip("/")
    )


def _normalize_next_path(next_path: str | None, *, fallback: str = "/dashboard") -> str:
    candidate = (next_path or "").strip()
    if not candidate.startswith("/"):
        return fallback
    return candidate


def _google_redirect_uri() -> str:
    return (
        (settings.GOOGLE_REDIRECT_URI or settings.GOOGLE_OAUTH_REDIRECT_URI or "")
        .strip()
    )


def _auth_error_redirect(error_code: str, next_path: str | None = None) -> RedirectResponse:
    base = _frontend_base_url()
    login_url = f"{base}/login" if base else "/auth/login"
    params = {"oauth_error": error_code}
    normalized_next = _normalize_next_path(next_path)
    if normalized_next:
        params["next"] = normalized_next
    url = f"{login_url}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


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
def login_page(request: Request, next: str = "/app/leads", reset: int = 0, error: int = 0):
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "next": next, "reset": bool(reset), "error": bool(error)},
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


@public_router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page_alias(request: Request, sent: int = 0):
    return forgot_password_page(request=request, sent=sent)


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


@public_router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page_alias(
    request: Request,
    token: str = "",
    db: Session = Depends(get_db),
):
    return reset_password_page(request=request, token=token, db=db)


# ---------- Form POST endpoints (cookie-setting) ----------


@router.post("/login")
async def login_form(
    request: Request,
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    next: str = Form("/app/leads"),
    db: Session = Depends(get_db),
):
    if _is_json_request(request):
        try:
            payload = LoginPayload.model_validate(await request.json())
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Invalid login payload") from exc
        email = payload.email
        password = payload.password
        next = payload.next or "/app/leads"

    if not email or not password:
        if _is_json_request(request):
            raise HTTPException(status_code=422, detail="Email and password are required")
        return RedirectResponse(url=f"/auth/login?next={next}&error=1", status_code=302)

    logger.info("AUTH_LOGIN_FORM_HIT email=%s", email)
    email_norm = email.lower().strip()
    user = db.query(User).filter(User.email == email_norm).first()

    if not user or not user.is_active or not verify_password(password, user.password_hash):
        logger.warning("AUTH_LOGIN_INVALID_CREDENTIALS email=%s", email_norm)
        if _is_json_request(request):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return RedirectResponse(url=f"/auth/login?next={next}&error=1", status_code=302)

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    if not next.startswith("/"):
        next = "/app/leads"

    logger.info("AUTH_LOGIN_SUCCESS user_id=%s tenant_id=%s", user.id, user.tenant_id)
    if _is_json_request(request):
        resp = JSONResponse(
            status_code=200,
            content={
                "user_id": user.id,
                "email": user.email,
                "tenant_id": user.tenant_id,
                "next": next,
            },
        )
        _set_auth_cookie(resp, token)
        return resp

    resp = RedirectResponse(url=next, status_code=302)
    _set_auth_cookie(resp, token)
    return resp


@router.post("/register")
async def register_form(
    request: Request,
    background_tasks: BackgroundTasks,
    company_name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    phone: str | None = Form(default=None),
    walls_rate_eur_per_sqm: float | None = Form(default=None),
    password: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if _is_json_request(request):
        try:
            payload = RegisterPayload.model_validate(await request.json())
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Invalid registration payload") from exc
        company_name = payload.company_name
        email = payload.email
        phone = payload.phone
        walls_rate_eur_per_sqm = payload.walls_rate_eur_per_sqm
        password = payload.password

    if not email or not password:
        if _is_json_request(request):
            raise HTTPException(status_code=422, detail="Email and password are required")
        return RedirectResponse(url="/auth/register", status_code=302)
    if len(password.strip()) < 8:
        if _is_json_request(request):
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        return RedirectResponse(url="/auth/register", status_code=302)

    logger.info("AUTH_REGISTER_FORM_HIT email=%s company_name=%s", email, company_name)
    company_name_clean = (company_name or "").strip() or "Mijn schildersbedrijf"
    email_norm = email.lower().strip()
    phone_clean = phone.strip() if phone else None

    existing = db.query(User).filter(User.email == email_norm).first()
    if existing:
        logger.warning("AUTH_REGISTER_EMAIL_EXISTS email=%s", email_norm)
        if _is_json_request(request):
            raise HTTPException(status_code=409, detail="An account with that email already exists")
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
        plan_code="core",
        subscription_status="trialing",
        trial_ends_at=trial_end,
        pricing_json=(
            {"walls_rate_eur_per_sqm": float(walls_rate_eur_per_sqm)}
            if walls_rate_eur_per_sqm is not None
            else {}
        ),
        enabled_verticals=["construction"],
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

    if _is_json_request(request):
        resp = JSONResponse(
            status_code=201,
            content={
                "user_id": user.id,
                "email": user.email,
                "tenant_id": user.tenant_id,
                "next": "/dashboard",
            },
        )
    else:
        resp = RedirectResponse(url="/onboarding/link", status_code=303)
    _set_auth_cookie(resp, token)
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

    return RedirectResponse(url="/forgot-password?sent=1", status_code=303)


@router.post("/password-reset/request")
def password_reset_request_api(
    payload: PasswordResetRequestPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email_norm = payload.email.lower().strip()
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
            logger.info("AUTH_RESET_REQUEST_API_ACCEPTED user_id=%s", user.id)
        else:
            db.commit()
            logger.info("AUTH_RESET_REQUEST_API_ACCEPTED_NON_EXISTENT_OR_INACTIVE")
    except Exception:
        logger.exception("AUTH_RESET_REQUEST_API_FAILED")
        db.rollback()

    return {
        "ok": True,
        "message": "Als dit e-mailadres bekend is, is er een e-mail met instructies verstuurd.",
    }


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


@router.post("/password-reset/confirm")
def password_reset_confirm_api(
    payload: PasswordResetConfirmPayload,
    db: Session = Depends(get_db),
):
    raw_token = (payload.token or "").strip()
    new_password = (payload.new_password or "").strip()
    user: User | None = None

    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    try:
        user_id = consume_password_reset_token_atomic(db=db, raw_token=raw_token)
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not user:
            db.rollback()
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user.password_hash = hash_password(new_password[:72])
        db.add(user)
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "AUTH_RESET_CONFIRM_API_FAILED user_id=%s",
            user.id if user is not None else None,
        )
        raise HTTPException(status_code=500, detail="Failed to reset password")

    logger.info("AUTH_RESET_CONFIRM_API_SUCCESS user_id=%s", user.id)
    return {"ok": True}


@router.get("/google/start")
def google_auth_start(next: str = "/dashboard"):
    if (
        not settings.GOOGLE_CLIENT_ID
        or not settings.GOOGLE_CLIENT_SECRET
        or not _google_redirect_uri()
    ):
        logger.error("AUTH_GOOGLE_NOT_CONFIGURED")
        return _auth_error_redirect("google_not_configured", next)

    normalized_next = _normalize_next_path(next)
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    resp = RedirectResponse(url=auth_url, status_code=302)
    resp.set_cookie(
        key="google_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=600,
        path="/",
    )
    resp.set_cookie(
        key="google_oauth_next",
        value=normalized_next,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=600,
        path="/",
    )
    return resp


@router.get("/google/callback")
def google_auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    saved_next = request.cookies.get("google_oauth_next") or "/dashboard"
    normalized_next = _normalize_next_path(saved_next)
    expected_state = request.cookies.get("google_oauth_state") or ""

    if error:
        logger.warning("AUTH_GOOGLE_DENIED error=%s", error)
        resp = _auth_error_redirect("google_cancelled", normalized_next)
    elif not code:
        logger.warning("AUTH_GOOGLE_MISSING_CODE")
        resp = _auth_error_redirect("google_callback_error", normalized_next)
    elif not state or not expected_state or not secrets.compare_digest(state, expected_state):
        logger.warning("AUTH_GOOGLE_INVALID_STATE")
        resp = _auth_error_redirect("google_invalid_state", normalized_next)
    else:
        try:
            token_payload = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _google_redirect_uri(),
            }
            with httpx.Client(timeout=15.0) as client:
                token_response = client.post(GOOGLE_TOKEN_URL, data=token_payload)
            if token_response.status_code >= 400:
                logger.warning(
                    "AUTH_GOOGLE_TOKEN_EXCHANGE_FAILED status=%s body=%s",
                    token_response.status_code,
                    token_response.text[:300],
                )
                resp = _auth_error_redirect("google_callback_error", normalized_next)
            else:
                access_token = token_response.json().get("access_token")
                if not access_token:
                    logger.warning("AUTH_GOOGLE_NO_ACCESS_TOKEN")
                    resp = _auth_error_redirect("google_callback_error", normalized_next)
                else:
                    with httpx.Client(timeout=15.0) as client:
                        userinfo_response = client.get(
                            GOOGLE_USERINFO_URL,
                            headers={"Authorization": f"Bearer {access_token}"},
                        )
                    if userinfo_response.status_code >= 400:
                        logger.warning(
                            "AUTH_GOOGLE_USERINFO_FAILED status=%s body=%s",
                            userinfo_response.status_code,
                            userinfo_response.text[:300],
                        )
                        resp = _auth_error_redirect("google_callback_error", normalized_next)
                    else:
                        profile = userinfo_response.json()
                        email = (profile.get("email") or "").lower().strip()
                        if not email:
                            logger.warning("AUTH_GOOGLE_EMAIL_MISSING")
                            resp = _auth_error_redirect("google_email_missing", normalized_next)
                        else:
                            user = db.query(User).filter(User.email == email).first()
                            if user and not user.is_active:
                                logger.warning("AUTH_GOOGLE_INACTIVE_USER email=%s", email)
                                resp = _auth_error_redirect("google_account_inactive", normalized_next)
                            else:
                                if not user:
                                    display_name = (profile.get("name") or "").strip() or "Mijn schildersbedrijf"
                                    base_slug = slugify(display_name) or "tenant"
                                    slug = base_slug
                                    counter = 2
                                    while db.query(Tenant).filter(Tenant.slug == slug).first():
                                        slug = f"{base_slug}-{counter}"
                                        counter += 1

                                    trial_start = datetime.now(timezone.utc)
                                    trial_end = trial_start + timedelta(days=14)
                                    tenant = Tenant(
                                        id=str(uuid4()),
                                        name=display_name,
                                        company_name=display_name,
                                        email=email,
                                        phone=None,
                                        slug=slug,
                                        plan_code="core",
                                        subscription_status="trialing",
                                        trial_ends_at=trial_end,
                                        pricing_json={},
                                        enabled_verticals=["construction"],
                                    )
                                    user = User(
                                        id=str(uuid4()),
                                        tenant_id=tenant.id,
                                        email=email,
                                        password_hash=hash_password(str(uuid4())),
                                        is_active=True,
                                        is_platform_admin=False,
                                        company_name=display_name,
                                    )
                                    db.add(tenant)
                                    db.add(user)
                                    db.commit()
                                    db.refresh(user)
                                    logger.info(
                                        "AUTH_GOOGLE_REGISTER_SUCCESS user_id=%s tenant_id=%s",
                                        user.id,
                                        user.tenant_id,
                                    )
                                token = create_access_token(
                                    user_id=user.id,
                                    tenant_id=user.tenant_id,
                                    email=user.email,
                                )
                                target = f"{_frontend_base_url()}{normalized_next}" if _frontend_base_url() else normalized_next
                                resp = RedirectResponse(url=target, status_code=302)
                                _set_auth_cookie(resp, token)
                                logger.info(
                                    "AUTH_GOOGLE_LOGIN_SUCCESS user_id=%s tenant_id=%s",
                                    user.id,
                                    user.tenant_id,
                                )
        except Exception:
            db.rollback()
            logger.exception("AUTH_GOOGLE_CALLBACK_FAILED")
            resp = _auth_error_redirect("google_callback_error", normalized_next)

    resp.delete_cookie("google_oauth_state", path="/")
    resp.delete_cookie("google_oauth_next", path="/")
    return resp


@router.post("/logout")
def logout(request: Request):
    if _is_json_request(request):
        resp = JSONResponse(status_code=200, content={"ok": True})
    else:
        resp = RedirectResponse(url="/auth/login", status_code=302)
    resp.delete_cookie("access_token", path="/")
    return resp


@router.get("/me")
def auth_me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email, "tenant_id": user.tenant_id}
