"""GLiNER zero-shot NER schema detector.

Proposes fields from generic entity labels found in the document.
Lazy-loads the model so the rest of the pipeline runs without GLiNER installed.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from server.core.document import Document, FieldCandidate

log = logging.getLogger(__name__)

_DEFAULT_LABELS = [
    "person",
    "organization",
    "money",
    "date",
    "invoice number",
    "purchase order number",
    "reference number",
    "email",
    "phone",
    "address",
    "percentage",
    "project name",
    "duration",
    "payment terms",
]

_LABEL_TO_TYPE = {
    "money": "currency",
    "date": "date",
    "email": "email",
    "phone": "phone",
    "percentage": "percentage",
    "invoice number": "id",
    "purchase order number": "id",
    "reference number": "id",
}


def _snake(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s


class NerDetector:
    name = "ner"

    def __init__(self, model_name: Optional[str] = None, threshold: float = 0.4, labels: Optional[list[str]] = None):
        self.model_name = model_name or os.getenv("GLINER_MODEL", "urchade/gliner_multi-v2.1")
        self.threshold = threshold
        self.labels = labels or _DEFAULT_LABELS
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from gliner import GLiNER
        except ImportError:
            log.warning("gliner not installed; NER detector disabled")
            return None
        try:
            self._model = GLiNER.from_pretrained(self.model_name)
        except Exception as e:
            log.warning("GLiNER model load failed: %s", e)
            self._model = None
        return self._model

    def propose(self, doc: Document) -> list[FieldCandidate]:
        if os.getenv("ENABLE_NER", "1") != "1":
            return []
        model = self._load()
        if model is None:
            return []

        text = (doc.raw_markdown or doc.raw_text)[:12000]  # cap for CPU latency
        if not text.strip():
            return []
        try:
            entities = model.predict_entities(text, self.labels, threshold=self.threshold)
        except Exception as e:
            log.warning("GLiNER predict failed: %s", e)
            return []

        seen: dict[str, FieldCandidate] = {}
        for ent in entities:
            label = ent.get("label") or ent.get("entity") or ""
            score = float(ent.get("score", 0.5))
            name = _snake(label)
            if not name:
                continue
            if name in seen:
                if score > seen[name].confidence:
                    seen[name].confidence = score
                continue
            seen[name] = FieldCandidate(
                name=name,
                data_type=_LABEL_TO_TYPE.get(label, "string"),
                description=f"NER label '{label}'",
                confidence=score,
                detected_by=self.name,
            )
        return list(seen.values())
