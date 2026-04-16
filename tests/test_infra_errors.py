"""
tests/test_infra_errors.py

Isolated unit tests for the error taxonomy in app.infra.errors.

Scope: classify_exception(), is_retryable(), is_terminal(), recoverability_hint().
No external I/O — all inputs are constructed in-process.
"""
from __future__ import annotations

import pytest

from app.infra.errors import (
    ErrorCategory,
    classify_exception,
    is_retryable,
    is_terminal,
    recoverability_hint,
)


# ---------------------------------------------------------------------------
# classify_exception — validation category
# ---------------------------------------------------------------------------

class TestClassifyValidation:
    """Python data/contract errors that should never be retried."""

    def test_value_error(self):
        assert classify_exception(ValueError("bad value")) == ErrorCategory.VALIDATION

    def test_type_error(self):
        assert classify_exception(TypeError("wrong type")) == ErrorCategory.VALIDATION

    def test_key_error(self):
        assert classify_exception(KeyError("missing_key")) == ErrorCategory.VALIDATION

    def test_attribute_error(self):
        assert classify_exception(AttributeError("no attr")) == ErrorCategory.VALIDATION

    def test_index_error(self):
        assert classify_exception(IndexError("out of range")) == ErrorCategory.VALIDATION


# ---------------------------------------------------------------------------
# classify_exception — permanent category
# ---------------------------------------------------------------------------

class TestClassifyPermanent:
    """Failures that require a code or config fix — never retry."""

    def test_file_not_found(self):
        assert classify_exception(FileNotFoundError("no file")) == ErrorCategory.PERMANENT

    def test_not_a_directory(self):
        assert classify_exception(NotADirectoryError("not a dir")) == ErrorCategory.PERMANENT

    def test_assertion_error(self):
        assert classify_exception(AssertionError("invariant broken")) == ErrorCategory.PERMANENT

    def test_not_implemented_error(self):
        assert classify_exception(NotImplementedError("stub")) == ErrorCategory.PERMANENT

    # Message-heuristic: phrases that imply a config/data issue
    def test_message_not_found(self):
        assert classify_exception(RuntimeError("resource not found")) == ErrorCategory.PERMANENT

    def test_message_not_configured(self):
        assert classify_exception(RuntimeError("service not configured")) == ErrorCategory.PERMANENT

    def test_message_missing(self):
        assert classify_exception(RuntimeError("config missing")) == ErrorCategory.PERMANENT

    def test_message_does_not_exist(self):
        assert classify_exception(RuntimeError("bucket does not exist")) == ErrorCategory.PERMANENT

    def test_message_invalid(self):
        assert classify_exception(RuntimeError("invalid region")) == ErrorCategory.PERMANENT


# ---------------------------------------------------------------------------
# classify_exception — transient category
# ---------------------------------------------------------------------------

class TestClassifyTransient:
    """Network / OS errors that may resolve on retry."""

    def test_connection_error(self):
        assert classify_exception(ConnectionError("refused")) == ErrorCategory.TRANSIENT

    def test_timeout_error(self):
        assert classify_exception(TimeoutError("timed out")) == ErrorCategory.TRANSIENT

    def test_os_error(self):
        assert classify_exception(OSError("io error")) == ErrorCategory.TRANSIENT

    def test_unknown_exception_defaults_to_transient(self):
        class WeirdError(Exception):
            pass
        assert classify_exception(WeirdError("unknown")) == ErrorCategory.TRANSIENT

    def test_runtime_error_without_permanent_phrase_is_transient(self):
        # "something exploded" does not match any permanent phrase
        assert classify_exception(RuntimeError("something exploded")) == ErrorCategory.TRANSIENT


# ---------------------------------------------------------------------------
# is_retryable / is_terminal
# ---------------------------------------------------------------------------

class TestIsRetryable:
    def test_transient_is_retryable(self):
        assert is_retryable(ConnectionError()) is True

    def test_timeout_is_retryable(self):
        assert is_retryable(TimeoutError()) is True

    def test_validation_is_not_retryable(self):
        assert is_retryable(ValueError("bad")) is False

    def test_permanent_is_not_retryable(self):
        assert is_retryable(FileNotFoundError()) is False

    def test_assertion_is_not_retryable(self):
        assert is_retryable(AssertionError()) is False


class TestIsTerminal:
    def test_validation_is_terminal(self):
        assert is_terminal(ValueError("bad")) is True

    def test_permanent_is_terminal(self):
        assert is_terminal(FileNotFoundError()) is True

    def test_transient_is_not_terminal(self):
        assert is_terminal(ConnectionError()) is False

    def test_unknown_is_not_terminal(self):
        class WeirdError(Exception):
            pass
        assert is_terminal(WeirdError()) is False


# ---------------------------------------------------------------------------
# recoverability_hint
# ---------------------------------------------------------------------------

class TestRecoverabilityHint:
    def test_transient_is_retryable(self):
        assert recoverability_hint("transient") == "retryable"

    def test_external_dep_is_retryable(self):
        assert recoverability_hint("external_dependency") == "retryable"

    def test_permanent_is_terminal(self):
        assert recoverability_hint("permanent") == "terminal"

    def test_validation_is_terminal(self):
        assert recoverability_hint("validation") == "terminal"

    def test_none_is_unknown(self):
        assert recoverability_hint(None) == "unknown"

    def test_garbage_string_is_unknown(self):
        assert recoverability_hint("not_a_real_category") == "unknown"
