"""LLM extractor — wraps the existing 2-stage Qwen pipeline."""

from __future__ import annotations

import logging
import os

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor

log = logging.getLogger(__name__)


class LlmExtractor(BaseExtractor):
    name = "llm"
    prior = 0.85

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        if os.getenv("ENABLE_LLM", "1") != "1":
            return []
        if not os.getenv("OPENROUTER_API_KEY"):
            return []
        if not schema:
            return []
        try:
            from server.extractor.models import DetectedField
            from server.llm.data_extractor import extract_fields
        except Exception as e:
            log.warning("LLM extractor unavailable: %s", e)
            return []

        # Map schema → DetectedField (existing legacy contract)
        detected = []
        for fc in schema:
            data_type = fc.data_type
            if data_type in ("currency", "id", "email", "phone", "percentage"):
                data_type = "string"
            detected.append(
                DetectedField(name=fc.name, data_type=data_type, description=fc.description)
            )

        text = doc.raw_markdown or doc.raw_text
        try:
            result = extract_fields(text, detected)
        except Exception as e:
            log.warning("LLM extraction failed: %s", e)
            return []

        out: list[Candidate] = []
        for f in getattr(result, "fields", []):
            if f.value is None:
                continue
            out.append(
                Candidate(
                    field=f.field_name,
                    value=f.value,
                    confidence=float(f.confidence or 0.5),
                    source=self.name,
                    evidence=Evidence(
                        method_detail="llm",
                        source_quote=f.source_quote,
                    ),
                )
            )
        return out
