"""Section-body extractor.

For each schema field whose name was detected by the OutlineDetector,
locate the heading element and aggregate the body paragraphs that follow it
(up to the next heading) into a single value.  This is what makes narrative
documents (specs, reports, contracts) actually return useful content.
"""

from __future__ import annotations

import re

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor

_HEADING_RE = re.compile(
    r"^\s*(?:section\s+)?"
    r"(\d+(?:\.\d+){0,3}|[A-Z])"
    r"[.)]?\s+"
    r"([A-Z][A-Za-z0-9][A-Za-z0-9 \-_/&'.,()]{1,80}?)\s*$",
    re.IGNORECASE,
)


def _snake(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()


class SectionExtractor(BaseExtractor):
    name = "section"
    prior = 0.85

    # Aggregate at most N body paragraphs per section to keep payload sane
    max_body_paras = 30
    max_value_chars = 1500

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        outline_fields = {fc.name for fc in schema if "outline" in (fc.detected_by or "")}
        if not outline_fields:
            return []

        # Find heading elements in document order
        headings: list[tuple[int, str, str]] = []  # (idx, snake_name, raw_text)
        for idx, el in enumerate(doc.elements):
            txt = (el.text or "").strip()
            if not txt or len(txt) > 120:
                continue
            m = _HEADING_RE.match(txt)
            if not m:
                continue
            name = _snake(m.group(2))
            if name in outline_fields:
                headings.append((idx, name, txt))

        if not headings:
            return []

        out: list[Candidate] = []
        for h_pos, (idx, name, _txt) in enumerate(headings):
            next_idx = headings[h_pos + 1][0] if h_pos + 1 < len(headings) else len(doc.elements)
            # Collect non-heading, non-empty paragraphs between this heading and the next
            body_parts: list[str] = []
            for el in doc.elements[idx + 1 : next_idx]:
                t = (el.text or "").strip()
                if not t:
                    continue
                if _HEADING_RE.match(t):  # nested heading we missed
                    continue
                body_parts.append(t)
                if len(body_parts) >= self.max_body_paras:
                    break

            value = " ".join(body_parts).strip()
            if not value:
                continue
            if len(value) > self.max_value_chars:
                value = value[: self.max_value_chars].rstrip() + "…"

            heading_el = doc.elements[idx]
            out.append(
                Candidate(
                    field=name,
                    value=value,
                    confidence=0.85,
                    source=self.name,
                    evidence=Evidence(
                        page=heading_el.page,
                        bbox=heading_el.bbox,
                        element_id=heading_el.element_id,
                        method_detail=f"section:{name}",
                    ),
                )
            )
        return out
