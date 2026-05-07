"""Build the final response payload."""

from __future__ import annotations

import re
from typing import Any

from server.core.document import Document, FieldCandidate

_HEADING_RE = re.compile(
    r"^\s*(?:section\s+)?"
    r"(\d+(?:\.\d+){0,3}|[A-Z])"
    r"[.)]?\s+"
    r"([A-Z][A-Za-z0-9][A-Za-z0-9 \-_/&'.,()]{1,80}?)\s*$",
    re.IGNORECASE,
)


def _detect_title(doc: Document) -> str | None:
    """First non-empty title-like element wins."""
    for el in doc.elements:
        t = (el.text or "").strip()
        if not t:
            continue
        if el.type in ("title", "heading"):
            return t
        # First substantive paragraph if no formal title
        if len(t) >= 5 and not _HEADING_RE.match(t):
            return t
    return None


def _build_outline(doc: Document) -> list[dict]:
    outline = []
    for el in doc.elements:
        t = (el.text or "").strip()
        if not t:
            continue
        m = _HEADING_RE.match(t)
        if not m:
            continue
        outline.append({
            "number": m.group(1),
            "title": m.group(2).strip(),
            "page": el.page,
            "element_id": el.element_id,
        })
    return outline


def build_output(
    doc: Document,
    schema: list[FieldCandidate],
    fields: dict[str, dict],
    flagged: list[str],
    file_metadata: dict,
) -> dict[str, Any]:
    title = _detect_title(doc)
    outline = _build_outline(doc)
    return {
        "document": {
            "type": _infer_doc_type(schema, fields, outline),
            "parse_method": doc.parse_method,
            "is_scanned": "ocr" in doc.parse_method,
            "title": title,
            "outline": outline,
            "metadata": file_metadata,
        },
        "schema": [
            {
                "name": fc.name,
                "data_type": fc.data_type,
                "description": fc.description,
                "confidence": fc.confidence,
                "detected_by": fc.detected_by,
            }
            for fc in schema
        ],
        "fields": fields,
        "flagged_fields": flagged,
        "tables": [t.model_dump() for t in doc.tables],
        "elements": [_element_dict(e) for e in doc.elements[:500]],  # cap to keep payload sane
        "elements_truncated": len(doc.elements) > 500,
    }


def _element_dict(el):
    d = el.model_dump()
    d.pop("children", None)
    return d


def _infer_doc_type(schema, fields, outline=None) -> str:
    names = set(fields.keys())
    if {"invoice_number", "total"} & names or any("invoice" in n for n in names):
        return "invoice"
    if {"sow_reference", "project_name", "effective_date"} & names:
        return "statement_of_work"
    if {"effective_date", "expiration_date"} & names:
        return "contract"
    # Heuristic: if it has a numbered outline of 3+ sections, call it a "report/spec"
    if outline and len(outline) >= 3:
        return "specification"
    return "unknown"
