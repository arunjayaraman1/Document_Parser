"""Base extractor + shared helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from server.core.document import Candidate, Document, FieldCandidate


class BaseExtractor(ABC):
    name: str = "base"
    prior: float = 0.5

    @abstractmethod
    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        ...


def synonyms_for(field_name: str) -> list[str]:
    """Generate human-readable synonyms from a snake_case field name.

    invoice_number → ["invoice number", "invoice no", "invoice #",
                      "invoice_number", "invoice"]
    """
    base = field_name.replace("_", " ").strip()
    if not base:
        return []
    syns = {base, field_name}
    parts = base.split()
    syns.add(parts[-1])  # last word
    if "number" in base:
        syns.add(base.replace("number", "no"))
        syns.add(base.replace("number", "#"))
        syns.add(base.replace("number", "").strip())
    if "date" in base and base != "date":
        syns.add(base.replace(" date", ""))
    return [s for s in syns if s]
