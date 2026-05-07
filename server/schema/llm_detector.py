"""LLM-based schema detector — wraps the existing 2-stage Qwen pipeline."""

from __future__ import annotations

import logging
import os

from server.core.document import Document, FieldCandidate

log = logging.getLogger(__name__)

_TYPE_MAP = {
    "string": "string",
    "number": "number",
    "date": "date",
    "boolean": "boolean",
    "list": "list",
}


class LlmDetector:
    name = "llm"

    def propose(self, doc: Document) -> list[FieldCandidate]:
        if os.getenv("ENABLE_LLM", "1") != "1":
            return []
        if not os.getenv("OPENROUTER_API_KEY"):
            return []
        try:
            from server.llm.schema_extractor import detect_schema
        except Exception as e:
            log.warning("LLM schema extractor unavailable: %s", e)
            return []
        text = doc.raw_markdown or doc.raw_text
        if not text.strip():
            return []
        try:
            schema = detect_schema(text)
        except Exception as e:
            log.warning("LLM schema detection failed: %s", e)
            return []

        results: list[FieldCandidate] = []
        for f in getattr(schema, "fields", []):
            results.append(
                FieldCandidate(
                    name=f.name,
                    data_type=_TYPE_MAP.get(f.data_type, "string"),
                    description=f.description,
                    confidence=float(getattr(schema, "confidence", 0.7)),
                    detected_by=self.name,
                )
            )
        return results
