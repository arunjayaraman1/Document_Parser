"""Keyword-proximity extractor — vocabulary derived from the schema, not hardcoded."""

from __future__ import annotations

import re

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor, synonyms_for


class KeywordExtractor(BaseExtractor):
    name = "keyword"
    prior = 0.75

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        text = doc.raw_markdown or doc.raw_text
        if not text:
            return []
        out: list[Candidate] = []
        for fc in schema:
            # Skip fields that came from outline detection — the section extractor
            # is far more accurate for those. Keyword matching on a section title
            # against the body markdown produces noise (e.g. matching "**" runs).
            if fc.detected_by and "outline" in fc.detected_by:
                continue
            # Try longest synonym first so "invoice number" is preferred over "invoice".
            for syn in sorted(synonyms_for(fc.name), key=lambda s: -len(s)):
                if len(syn) < 2:
                    continue
                pattern = re.compile(
                    r"(?<![A-Za-z0-9])" + re.escape(syn) + r"\s*[:\-]?\s*(.{1,100}?)(?:\n|\r|$)",
                    re.IGNORECASE,
                )
                m = pattern.search(text)
                if not m:
                    continue
                value = re.sub(r"[.,;:]*\s*$", "", m.group(1).strip())
                if not value or len(value) < 2:
                    continue
                el = self._locate_element(syn, value, doc)
                ev = Evidence(method_detail=f"keyword:{syn}")
                if el is not None:
                    ev.element_id = el.element_id
                    ev.page = el.page
                    ev.bbox = el.bbox
                out.append(
                    Candidate(
                        field=fc.name,
                        value=value,
                        confidence=0.78,
                        source=self.name,
                        evidence=ev,
                    )
                )
                break  # take first synonym match per field
        return out

    @staticmethod
    def _locate_element(label: str, value: str, doc: Document):
        for el in doc.elements:
            if not el.text:
                continue
            t = el.text.lower()
            if label.lower() in t or value.lower() in t:
                return el
        return None
