"""
app/infra/errors.py
-------------------
Error taxonomy for engine and Celery task execution.

Four categories:
  TRANSIENT           - network blips, timeouts, transient 5xx -> retry
  PERMANENT           - bad config, missing tenant, 4xx -> do not retry
  VALIDATION          - malformed / missing input data -> do not retry
  EXTERNAL_DEPENDENCY - third-party API unavailable (HubSpot, S3) -> retry with higher backoff

Usage:
    from app.infra.errors import classify_exception, is_retryable, ErrorCategory

    category = classify_exception(exc)         # -> ErrorCategory
    if is_retryable(exc):
        ...
"""
from __future__ import annotations

import enum
from typing import Optional


class ErrorCategory(str, enum.Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    VALIDATION = "validation"
    EXTERNAL_DEPENDENCY = "external_dependency"


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_exception(exc: BaseException) -> ErrorCategory:
    """Return the ErrorCategory that best describes *exc*."""
    exc_type = type(exc)
    module = getattr(exc_type, "__module__", "") or ""
    msg = str(exc).lower()

    # --- requests HTTP errors (optional dep — skip if not installed) ---
    try:
        import requests.exceptions as req_exc  # noqa: PLC0415
        if isinstance(exc, req_exc.Timeout):
            return ErrorCategory.TRANSIENT
        if isinstance(exc, req_exc.ConnectionError):
            return ErrorCategory.TRANSIENT
        if isinstance(exc, req_exc.HTTPError):
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status is not None:
                if status == 429:
                    return ErrorCategory.TRANSIENT   # rate-limited
                if 500 <= status < 600:
                    return ErrorCategory.TRANSIENT
                if 400 <= status < 500:
                    return ErrorCategory.PERMANENT
    except ImportError:
        pass

    # --- botocore / boto3 (S3, etc.) ---
    if "botocore" in module or "boto3" in module:
        exc_name = exc_type.__name__
        if exc_name in ("ConnectTimeoutError", "ReadTimeoutError", "EndpointConnectionError"):
            return ErrorCategory.TRANSIENT
        if exc_name == "ClientError":
            error_code: str = ""
            try:
                error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
            except (AttributeError, KeyError, TypeError):
                pass
            _permanent_codes = {
                "NoSuchKey", "NoSuchBucket", "InvalidArgument",
                "AccessDenied", "InvalidRequest", "NoSuchEntity",
            }
            if error_code in _permanent_codes:
                return ErrorCategory.PERMANENT
        return ErrorCategory.EXTERNAL_DEPENDENCY

    # --- Python stdlib: bad data / contract violations -> validation ---
    if exc_type in (ValueError, TypeError):
        return ErrorCategory.VALIDATION
    if exc_type in (KeyError, AttributeError, IndexError):
        return ErrorCategory.VALIDATION

    # --- stdlib: clearly permanent ---
    if exc_type in (FileNotFoundError, NotADirectoryError, AssertionError, NotImplementedError):
        return ErrorCategory.PERMANENT

    # --- Heuristic: message content implies permanent failure ---
    _permanent_phrases = ("not found", "not configured", "missing", "does not exist", "invalid")
    if any(p in msg for p in _permanent_phrases):
        return ErrorCategory.PERMANENT

    # --- stdlib: connection / timeout builtins ---
    if exc_type in (ConnectionError, TimeoutError, OSError):
        return ErrorCategory.TRANSIENT

    # Unknown -> treat as transient; one retry beats zero.
    # Callers that want strict behaviour can check the category themselves.
    return ErrorCategory.TRANSIENT


def is_retryable(exc: BaseException) -> bool:
    """Return True when *exc* belongs to a retryable category."""
    return classify_exception(exc) in (
        ErrorCategory.TRANSIENT,
        ErrorCategory.EXTERNAL_DEPENDENCY,
    )


def is_terminal(exc: BaseException) -> bool:
    """Return True when this failure cannot be resolved by retrying.

    Terminal failures require a code or data fix before the job can succeed.
    Retryable failures (TRANSIENT, EXTERNAL_DEPENDENCY) may succeed if re-run.
    """
    return classify_exception(exc) in (
        ErrorCategory.PERMANENT,
        ErrorCategory.VALIDATION,
    )


# Recoverability hint strings — used by API responses and log messages.
_RECOVERABILITY: dict[str, str] = {
    ErrorCategory.TRANSIENT.value: "retryable",
    ErrorCategory.EXTERNAL_DEPENDENCY.value: "retryable",
    ErrorCategory.PERMANENT.value: "terminal",
    ErrorCategory.VALIDATION.value: "terminal",
}


def recoverability_hint(error_category: Optional[str]) -> str:
    """Human-readable recoverability label for an error_category string.

    Returns one of: ``"retryable"`` | ``"terminal"`` | ``"unknown"``.
    """
    if error_category is None:
        return "unknown"
    return _RECOVERABILITY.get(error_category, "unknown")


# ---------------------------------------------------------------------------
# Retry backoff presets per category
# ---------------------------------------------------------------------------

#: (attempts, base_s, factor, cap_s) — passed directly to retry_on()
RETRY_PARAMS: dict[ErrorCategory, tuple[int, float, float, float]] = {
    ErrorCategory.TRANSIENT: (3, 0.5, 2.0, 5.0),
    ErrorCategory.EXTERNAL_DEPENDENCY: (3, 1.0, 2.0, 10.0),
    ErrorCategory.PERMANENT: (1, 0.0, 1.0, 0.0),
    ErrorCategory.VALIDATION: (1, 0.0, 1.0, 0.0),
}
