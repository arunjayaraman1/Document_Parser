"""Heuristic schema detector — finds candidate fields with no LLM and no NER.

Looks for:
  - "Label: Value" pairs in lines
  - Table headers
  - Recognized data types (date / currency / email / phone / percentage)
"""

from __future__ import annotations

import re

from server.core.document import Document, FieldCandidate

# A real KV pair MUST use a colon — dash is too ambiguous (e.g. "hands-on")
# and produces noise on narrative docs. Label must contain at least one space
# OR be at least 3 chars to filter out numeric list markers like "1." / "5.1".
_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _#/\.\-]{1,40})\s*:\s*(\S.+?)\s*$")

_DATE_HINT = re.compile(
    r"(?:\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b)",
    re.I,
)
_CURRENCY_HINT = re.compile(r"(?:\$|€|£|¥|USD|EUR|GBP|INR)\s?[\d,]+(?:\.\d{1,2})?", re.I)
_EMAIL_HINT = re.compile(r"[\w.+\-]+@[\w\-]+\.[A-Za-z]{2,}")
_PHONE_HINT = re.compile(r"\+?\d[\d\-\s().]{6,}\d")
_PCT_HINT = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")


def _snake(label: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", label.strip()).strip("_")
    return s.lower()


def _infer_type(value: str) -> str:
    if _DATE_HINT.search(value):
        return "date"
    if _CURRENCY_HINT.search(value):
        return "currency"
    if _EMAIL_HINT.search(value):
        return "email"
    if _PCT_HINT.search(value):
        return "percentage"
    if _PHONE_HINT.search(value):
        return "phone"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
        return "number"
    return "string"


class HeuristicDetector:
    name = "heuristic"

    def propose(self, doc: Document) -> list[FieldCandidate]:
        seen: dict[str, FieldCandidate] = {}
        text = doc.raw_markdown or doc.raw_text or "\n".join(e.text for e in doc.elements if e.text)

        # Pass 1: KV pairs from text lines
        for line in text.splitlines():
            m = _KV_RE.match(line)
            if not m:
                continue
            label, value = m.group(1).strip(), m.group(2).strip()
            if not value or len(value) > 200:
                continue
            # Reject numeric/heading labels: "1", "5.1", "11.2"
            if re.fullmatch(r"[\d.\s]+", label):
                continue
            # Reject very short single-word labels that are usually section titles
            if len(label) < 3:
                continue
            name = _snake(label)
            if not name or len(name) < 3:
                continue
            if name in seen:
                continue
            seen[name] = FieldCandidate(
                name=name,
                data_type=_infer_type(value),
                description=f"Detected from KV pair: '{label}'",
                confidence=0.7,
                detected_by=self.name,
            )

        # Pass 2: Table headers → fields
        for tbl in doc.tables:
            for cell in tbl.header_row():
                if not cell.text:
                    continue
                name = _snake(cell.text)
                if not name or len(name) < 2 or name in seen:
                    continue
                seen[name] = FieldCandidate(
                    name=name,
                    data_type="string",
                    description=f"Detected from table header on page {tbl.page}",
                    confidence=0.65,
                    detected_by=self.name,
                )

        return list(seen.values())
