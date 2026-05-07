"""Outline-based schema detector.

Recognizes numbered/lettered section headings ("1. Introduction", "5.1 Document
Chunking", "11.2 README.md") and exposes each section as a candidate field whose
value is the section body.  This is the right structural schema for narrative
documents — specs, reports, contracts — that lack form-style key/value pairs.
"""

from __future__ import annotations

import re

from server.core.document import Document, FieldCandidate

# Matches: "1. Introduction", "5.1 Document Chunking", "11.2 README.md",
# "A. Scope", "Section 4 — Technology Requirements"
_HEADING_RE = re.compile(
    r"^\s*(?:section\s+)?"
    r"(?P<num>\d+(?:\.\d+){0,3}|[A-Z])"
    r"[.)]?\s+"
    r"(?P<title>[A-Z][A-Za-z0-9][A-Za-z0-9 \-_/&'.,()]{1,80}?)\s*$",
    re.IGNORECASE,
)


def _snake(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()


class OutlineDetector:
    name = "outline"

    def propose(self, doc: Document) -> list[FieldCandidate]:
        # Walk elements in order — preserves document flow.
        headings = []
        for el in doc.elements:
            txt = (el.text or "").strip()
            if not txt or len(txt) > 120:
                continue
            m = _HEADING_RE.match(txt)
            if not m:
                continue
            headings.append((el.element_id, m.group("num"), m.group("title").strip()))

        # Need at least 2 headings to call it an outline
        if len(headings) < 2:
            return []

        out: list[FieldCandidate] = []
        seen: set[str] = set()
        for _eid, num, title in headings:
            name = _snake(title)
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(
                FieldCandidate(
                    name=name,
                    data_type="string",
                    description=f"Section '{num}. {title}'",
                    confidence=0.8,
                    detected_by=self.name,
                )
            )
        return out
