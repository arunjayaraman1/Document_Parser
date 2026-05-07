"""NER value extractor — uses GLiNER with the discovered field names as zero-shot labels."""

from __future__ import annotations

import logging
import os
from typing import Optional

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor

log = logging.getLogger(__name__)


class NerExtractor(BaseExtractor):
    name = "ner"
    prior = 0.7

    def __init__(self, model_name: Optional[str] = None, threshold: float = 0.4):
        self.model_name = model_name or os.getenv("GLINER_MODEL", "urchade/gliner_multi-v2.1")
        self.threshold = threshold
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from gliner import GLiNER
        except ImportError:
            return None
        try:
            self._model = GLiNER.from_pretrained(self.model_name)
        except Exception as e:
            log.warning("GLiNER load failed: %s", e)
            self._model = None
        return self._model

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        if os.getenv("ENABLE_NER", "1") != "1" or not schema:
            return []
        model = self._load()
        if model is None:
            return []
        labels = [fc.name.replace("_", " ") for fc in schema]
        text = (doc.raw_markdown or doc.raw_text)[:12000]
        if not text.strip():
            return []
        try:
            entities = model.predict_entities(text, labels, threshold=self.threshold)
        except Exception as e:
            log.warning("GLiNER predict failed: %s", e)
            return []

        out: list[Candidate] = []
        seen: set[str] = set()
        for ent in entities:
            label = (ent.get("label") or "").lower()
            field = label.replace(" ", "_")
            if field in seen:
                continue
            value = ent.get("text", "")
            score = float(ent.get("score", 0.5))
            if not value:
                continue
            seen.add(field)
            el = self._locate(value, doc)
            ev = Evidence(method_detail=f"ner:{label}", source_quote=value)
            if el is not None:
                ev.element_id = el.element_id
                ev.page = el.page
                ev.bbox = el.bbox
            out.append(
                Candidate(
                    field=field,
                    value=value,
                    confidence=score,
                    source=self.name,
                    evidence=ev,
                )
            )
        return out

    @staticmethod
    def _locate(value: str, doc: Document):
        for el in doc.elements:
            if el.text and value in el.text:
                return el
        return None
