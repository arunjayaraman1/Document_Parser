"""Generic regex extractor — patterns are typed by data_type, not by doc type."""

from __future__ import annotations

import re

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor

_PATTERNS: dict[str, re.Pattern] = {
    "date": re.compile(
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}"
        r"|\b\d{4}-\d{2}-\d{2}\b"
        r"|\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "currency": re.compile(
        r"(?:\$|USD|EUR|GBP|INR|€|£|¥)\s*[\d,]+(?:\.\d{2})?"
        r"|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)"
    ),
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "percentage": re.compile(r"\d+(?:\.\d+)?\s*%"),
    "number": re.compile(r"-?\d+(?:\.\d+)?"),
    "id": re.compile(r"\b[A-Z0-9][A-Z0-9\-]{3,30}\b"),
}


def _locate(value: str, doc: Document):
    """Find the element containing the matched substring."""
    for el in doc.elements:
        if el.text and value in el.text:
            return el
    return None


class RegexExtractor(BaseExtractor):
    name = "regex"
    prior = 0.95

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        text = doc.raw_markdown or doc.raw_text
        if not text:
            return []
        out: list[Candidate] = []
        for fc in schema:
            pat = _PATTERNS.get(fc.data_type)
            if pat is None:
                continue
            m = pat.search(text)
            if not m:
                continue
            value = m.group(0)
            el = _locate(value, doc)
            ev = Evidence(method_detail=f"regex:{fc.data_type}")
            if el is not None:
                ev.element_id = el.element_id
                ev.page = el.page
                ev.bbox = el.bbox
            out.append(
                Candidate(
                    field=fc.name,
                    value=value,
                    confidence=0.95,
                    source=self.name,
                    evidence=ev,
                )
            )
        return out
