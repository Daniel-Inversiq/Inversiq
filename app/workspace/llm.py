"""
app/workspace/llm.py

Thin Anthropic API wrapper for workspace pipeline steps.

Returns structured JSON via tool_use forcing — no parsing of free text.
All functions are synchronous; call from background worker threads.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.core.settings import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap for extraction; swap to sonnet for higher accuracy


def _client() -> anthropic.Anthropic:
    key = settings.ANTHROPIC_API_KEY
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=key)


def classify_document(filename: str, text_sample: str) -> dict[str, Any]:
    """
    Classify a document given its filename and a text sample (first ~2000 chars).

    Returns: {"doc_type": str, "confidence": float (0-1), "reasoning": str}
    """
    from app.workspace.schemas import DOCUMENT_TYPES

    type_list = "\n".join(f"- {k}: {v}" for k, v in DOCUMENT_TYPES.items())
    tool = {
        "name": "classify_document",
        "description": "Classify the document type",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "string",
                    "enum": list(DOCUMENT_TYPES.keys()),
                    "description": "The document type",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in classification from 0.0 to 1.0",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One sentence explaining the classification decision",
                },
            },
            "required": ["doc_type", "confidence", "reasoning"],
        },
    }

    prompt = (
        f"You are classifying a document for a commercial real estate investment platform.\n\n"
        f"Filename: {filename}\n\n"
        f"Document text (first portion):\n{text_sample[:2000]}\n\n"
        f"Available document types:\n{type_list}\n\n"
        f"Classify this document. Choose the single best matching type."
    )

    response = _client().messages.create(
        model=_MODEL,
        max_tokens=256,
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify_document"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input  # type: ignore[return-value]

    return {"doc_type": "other", "confidence": 0.0, "reasoning": "No classification returned"}


def extract_document(doc_type: str, text: str) -> dict[str, Any]:
    """
    Extract structured data from document text using the schema for doc_type.

    Returns: {"fields": {...}, "confidence": float, "missing_required": [...]}
    """
    from app.workspace.schemas import get_schema

    schema = get_schema(doc_type)
    fields_desc = "\n".join(f"- {k}: {v}" for k, v in schema["fields"].items())
    required = schema.get("required", [])

    properties: dict[str, Any] = {}
    for field_name, field_desc in schema["fields"].items():
        if field_name == "tenants":
            properties[field_name] = {
                "type": "array",
                "description": field_desc,
                "items": {
                    "type": "object",
                    "properties": {
                        "tenant_name": {"type": "string"},
                        "sqm": {"type": ["number", "null"]},
                        "passing_rent_annual": {"type": ["number", "null"]},
                        "lease_start": {"type": ["string", "null"]},
                        "lease_expiry": {"type": ["string", "null"]},
                        "break_date": {"type": ["string", "null"]},
                        "erv_psm": {"type": ["number", "null"]},
                    },
                    "required": ["tenant_name"],
                },
            }
        elif field_name == "major_issues":
            properties[field_name] = {"type": "array", "items": {"type": "string"}, "description": field_desc}
        elif field_name == "key_figures":
            properties[field_name] = {"type": "array", "items": {"type": "string"}, "description": field_desc}
        else:
            properties[field_name] = {"type": ["string", "number", "null"], "description": field_desc}

    properties["confidence"] = {
        "type": "number",
        "description": "Your confidence in the extraction accuracy from 0.0 to 1.0",
    }
    properties["extraction_notes"] = {
        "type": "string",
        "description": "Brief note on any fields that were uncertain or ambiguous",
    }

    tool = {
        "name": "extract_fields",
        "description": f"Extract structured fields from a {doc_type.replace('_', ' ')} document",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": ["confidence"],
        },
    }

    prompt = (
        f"You are extracting structured data from a commercial real estate document.\n"
        f"Document type: {doc_type.replace('_', ' ')}\n\n"
        f"Fields to extract:\n{fields_desc}\n\n"
        f"Document text:\n{text[:8000]}\n\n"
        f"Extract all available fields. Use null for fields not found in the document. "
        f"For numeric fields extract numbers only (no currency symbols). "
        f"For dates use YYYY-MM-DD format."
    )

    response = _client().messages.create(
        model=_MODEL,
        max_tokens=2048,
        tools=[tool],
        tool_choice={"type": "tool", "name": "extract_fields"},
        messages=[{"role": "user", "content": prompt}],
    )

    result: dict[str, Any] = {}
    for block in response.content:
        if block.type == "tool_use":
            result = dict(block.input)  # type: ignore[arg-type]
            break

    confidence = float(result.pop("confidence", 0.5))
    result.pop("extraction_notes", None)

    missing = [f for f in required if not result.get(f)]

    return {
        "fields": result,
        "confidence": confidence,
        "missing_required": missing,
    }
