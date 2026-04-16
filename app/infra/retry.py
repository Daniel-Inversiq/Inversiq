# app/infra/retry.py
import random
import time
import structlog
from typing import Callable, TypeVar, Optional

T = TypeVar("T")
_log = structlog.get_logger("inversiq.retry")

def _sleep_with_jitter(base: float, factor: float, attempt: int, cap: float) -> float:
    # exponential backoff with jitter
    delay = min(base * (factor ** attempt), cap)
    jitter = random.uniform(0, delay * 0.25)
    return delay + jitter

def retry_on(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base: float = 0.2,
    factor: float = 2.0,
    cap: float = 2.0,
    is_retryable: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # type: ignore
            if is_retryable and not is_retryable(e):
                raise
            last_exc = e
            if i == attempts - 1:
                break
            sleep_s = _sleep_with_jitter(base, factor, i, cap)
            if on_retry:
                on_retry(i + 1, e, sleep_s)
            else:
                _log.warning("retry_attempt", attempt=i + 1, sleep_s=round(sleep_s, 2), exc=repr(e))
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc

def retryable(
    *,
    attempts: int = 3,
    base: float = 0.2,
    factor: float = 2.0,
    cap: float = 2.0,
    is_retryable: Optional[Callable[[Exception], bool]] = None,
):
    """Decorator variant of retry_on."""
    def _wrap(func: Callable[..., T]) -> Callable[..., T]:
        def _inner(*args, **kwargs) -> T:
            return retry_on(
                lambda: func(*args, **kwargs),
                attempts=attempts,
                base=base,
                factor=factor,
                cap=cap,
                is_retryable=is_retryable,
            )
        return _inner
    return _wrap


def retry_on_transient(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base: float = 0.5,
    cap: float = 5.0,
) -> T:
    """Convenience wrapper: retry *fn* only on transient/external-dependency errors.

    Uses the project error taxonomy from app.infra.errors so callers don't
    need to wire up the predicate themselves.
    """
    from app.infra.errors import is_retryable  # local import avoids circular dep
    return retry_on(fn, attempts=attempts, base=base, factor=2.0, cap=cap, is_retryable=is_retryable)
