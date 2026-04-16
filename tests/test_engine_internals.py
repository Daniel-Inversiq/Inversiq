"""
tests/test_engine_internals.py

Unit tests for pure helper functions inside inversiq.engine.runner.

Scope: _lightweight() and _parse_error().
These are implementation-private but critical enough to test directly
because they control what gets written into DB snapshot columns.
"""
from __future__ import annotations

import pytest

from inversiq.engine.runner import _lightweight, _parse_error


# ---------------------------------------------------------------------------
# _lightweight — JSON snapshot capping
# ---------------------------------------------------------------------------

class TestLightweight:

    def test_empty_dict_returns_empty(self):
        assert _lightweight({}) == {}

    def test_simple_values_pass_through(self):
        data = {"a": 1, "b": "hello", "c": True, "d": None}
        result = _lightweight(data)
        assert result == data

    def test_long_string_is_truncated_at_400_chars(self):
        long_str = "x" * 500
        result = _lightweight({"key": long_str})
        assert result["key"].endswith("…")
        # Content before the ellipsis is exactly 400 chars
        assert len(result["key"]) == 401  # 400 chars + "…" (1 char)
        assert result["key"][:400] == "x" * 400

    def test_short_string_is_not_truncated(self):
        s = "x" * 399
        result = _lightweight({"key": s})
        assert result["key"] == s

    def test_string_at_exact_limit_is_not_truncated(self):
        s = "x" * 400
        result = _lightweight({"key": s})
        assert result["key"] == s

    def test_dict_value_is_replaced_with_placeholder(self):
        result = _lightweight({"nested": {"a": 1, "b": 2}})
        assert result["nested"] == "<dict len=2>"

    def test_list_value_is_replaced_with_placeholder(self):
        result = _lightweight({"items": [1, 2, 3, 4]})
        assert result["items"] == "<list len=4>"

    def test_empty_dict_value_placeholder(self):
        result = _lightweight({"nested": {}})
        assert result["nested"] == "<dict len=0>"

    def test_keys_beyond_20_are_dropped(self):
        data = {str(i): i for i in range(25)}
        result = _lightweight(data)
        assert len(result) == 20

    def test_exactly_20_keys_all_kept(self):
        data = {str(i): i for i in range(20)}
        result = _lightweight(data)
        assert len(result) == 20

    def test_original_dict_is_not_mutated(self):
        data = {"key": "x" * 500}
        _lightweight(data)
        assert data["key"] == "x" * 500

    def test_numeric_values_pass_through_unchanged(self):
        result = _lightweight({"n": 42, "f": 3.14})
        assert result["n"] == 42
        assert result["f"] == 3.14


# ---------------------------------------------------------------------------
# _parse_error — "ExcType: message" splitter
# ---------------------------------------------------------------------------

class TestParseError:

    def test_none_input_returns_none_none(self):
        assert _parse_error(None) == (None, None)

    def test_empty_string_returns_none_none(self):
        assert _parse_error("") == (None, None)

    def test_standard_format_splits_correctly(self):
        exc_type, msg = _parse_error("ValueError: bad input")
        assert exc_type == "ValueError"
        assert msg == "bad input"

    def test_message_with_colon_space_inside(self):
        exc_type, msg = _parse_error("RuntimeError: disk: full")
        assert exc_type == "RuntimeError"
        assert msg == "disk: full"

    def test_plain_string_without_separator(self):
        exc_type, msg = _parse_error("something went wrong")
        assert exc_type is None
        assert msg == "something went wrong"

    def test_non_identifier_prefix_treated_as_plain_message(self):
        # "123 Error: msg" — prefix "123 Error" is not an identifier
        exc_type, msg = _parse_error("123 Error: something")
        assert exc_type is None
        assert msg == "123 Error: something"

    def test_identifier_with_underscores_is_valid_type(self):
        exc_type, msg = _parse_error("My_Custom_Error: details here")
        assert exc_type == "My_Custom_Error"
        assert msg == "details here"

    def test_message_only_colon_no_space(self):
        # "ValueError:badmsg" — no ": " separator → treated as plain string
        exc_type, msg = _parse_error("ValueError:badmsg")
        assert exc_type is None
        assert msg == "ValueError:badmsg"
