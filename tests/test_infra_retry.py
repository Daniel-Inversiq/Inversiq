"""
tests/test_infra_retry.py

Isolated unit tests for app.infra.retry.

Scope: retry_on(), retryable decorator, retry_on_transient().
time.sleep is patched so tests run instantly.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.infra.retry import retry_on, retryable, retry_on_transient


# ---------------------------------------------------------------------------
# retry_on — core retry loop
# ---------------------------------------------------------------------------

class TestRetryOn:

    def test_success_on_first_attempt_returns_value(self):
        fn = MagicMock(return_value=42)
        assert retry_on(fn, attempts=3) == 42
        assert fn.call_count == 1

    def test_retries_on_failure_then_succeeds(self):
        fn = MagicMock(side_effect=[RuntimeError("boom"), RuntimeError("boom"), 99])
        with patch("app.infra.retry.time.sleep"):
            result = retry_on(fn, attempts=3)
        assert result == 99
        assert fn.call_count == 3

    def test_raises_after_exhausting_all_attempts(self):
        fn = MagicMock(side_effect=RuntimeError("always fails"))
        with patch("app.infra.retry.time.sleep"):
            with pytest.raises(RuntimeError, match="always fails"):
                retry_on(fn, attempts=3)
        assert fn.call_count == 3

    def test_single_attempt_raises_without_sleeping(self):
        fn = MagicMock(side_effect=RuntimeError("once"))
        with patch("app.infra.retry.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError):
                retry_on(fn, attempts=1)
        mock_sleep.assert_not_called()
        assert fn.call_count == 1

    def test_does_not_retry_when_is_retryable_returns_false(self):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            retry_on(fn, attempts=3, is_retryable=lambda e: False)
        # Raised on the first attempt, not retried
        assert fn.call_count == 1

    def test_retries_when_is_retryable_returns_true(self):
        fn = MagicMock(side_effect=[RuntimeError("transient"), "ok"])
        with patch("app.infra.retry.time.sleep"):
            result = retry_on(fn, attempts=2, is_retryable=lambda e: True)
        assert result == "ok"
        assert fn.call_count == 2

    def test_on_retry_callback_receives_attempt_exc_and_sleep(self):
        callback = MagicMock()
        fn = MagicMock(side_effect=[RuntimeError("boom"), "ok"])
        with patch("app.infra.retry.time.sleep"):
            retry_on(fn, attempts=2, on_retry=callback)
        callback.assert_called_once()
        attempt_num, exc, sleep_s = callback.call_args[0]
        assert attempt_num == 1
        assert isinstance(exc, RuntimeError)
        assert isinstance(sleep_s, float)
        assert sleep_s >= 0

    def test_on_retry_not_called_on_success(self):
        callback = MagicMock()
        fn = MagicMock(return_value="ok")
        retry_on(fn, attempts=3, on_retry=callback)
        callback.assert_not_called()

    def test_sleep_called_between_retries(self):
        fn = MagicMock(side_effect=[RuntimeError(), RuntimeError(), "ok"])
        with patch("app.infra.retry.time.sleep") as mock_sleep:
            retry_on(fn, attempts=3)
        # sleep is called once after attempt 1, once after attempt 2
        assert mock_sleep.call_count == 2


# ---------------------------------------------------------------------------
# retryable decorator
# ---------------------------------------------------------------------------

class TestRetryableDecorator:

    def test_decorated_function_returns_value(self):
        @retryable(attempts=3)
        def always_ok():
            return "result"

        assert always_ok() == "result"

    def test_decorated_function_passes_args_and_kwargs(self):
        @retryable(attempts=2)
        def add(a, b=0):
            return a + b

        assert add(3, b=4) == 7

    def test_decorated_function_retries_and_succeeds(self):
        call_count = {"n": 0}

        @retryable(attempts=3)
        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("transient")
            return "done"

        with patch("app.infra.retry.time.sleep"):
            result = flaky()

        assert result == "done"
        assert call_count["n"] == 3

    def test_decorated_function_raises_after_exhaustion(self):
        @retryable(attempts=2)
        def always_fails():
            raise RuntimeError("nope")

        with patch("app.infra.retry.time.sleep"):
            with pytest.raises(RuntimeError, match="nope"):
                always_fails()


# ---------------------------------------------------------------------------
# retry_on_transient — integration with error taxonomy
# ---------------------------------------------------------------------------

class TestRetryOnTransient:

    def test_succeeds_on_first_try(self):
        fn = MagicMock(return_value="ok")
        result = retry_on_transient(fn)
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_connection_error(self):
        """ConnectionError is TRANSIENT — should retry."""
        fn = MagicMock(side_effect=[ConnectionError("transient"), "ok"])
        with patch("app.infra.retry.time.sleep"):
            result = retry_on_transient(fn, attempts=2)
        assert result == "ok"
        assert fn.call_count == 2

    def test_retries_on_timeout_error(self):
        """TimeoutError is TRANSIENT — should retry."""
        fn = MagicMock(side_effect=[TimeoutError("timeout"), "done"])
        with patch("app.infra.retry.time.sleep"):
            result = retry_on_transient(fn, attempts=2)
        assert result == "done"

    def test_does_not_retry_on_value_error(self):
        """ValueError is VALIDATION — not retryable."""
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            retry_on_transient(fn, attempts=3)
        assert fn.call_count == 1

    def test_does_not_retry_on_file_not_found(self):
        """FileNotFoundError is PERMANENT — not retryable."""
        fn = MagicMock(side_effect=FileNotFoundError("no file"))
        with pytest.raises(FileNotFoundError):
            retry_on_transient(fn, attempts=3)
        assert fn.call_count == 1

    def test_raises_after_exhausting_transient_retries(self):
        fn = MagicMock(side_effect=ConnectionError("always down"))
        with patch("app.infra.retry.time.sleep"):
            with pytest.raises(ConnectionError, match="always down"):
                retry_on_transient(fn, attempts=3)
        assert fn.call_count == 3
