"""Spatial extractor — bbox geometry: find label, take nearest element to its right on the same line."""

from __future__ import annotations

from server.core.document import Candidate, Document, Evidence, FieldCandidate
from .base import BaseExtractor, synonyms_for


class SpatialExtractor(BaseExtractor):
    name = "spatial"
    prior = 0.8

    same_line_tol = 6.0
    max_gap = 250.0

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        elements = [e for e in doc.elements if e.bbox is not None and e.text]
        if not elements:
            return []
        out: list[Candidate] = []
        used_value_ids: set[str] = set()

        for fc in schema:
            label_el = None
            matched_label = None
            for syn in synonyms_for(fc.name):
                if len(syn) < 2:
                    continue
                for el in elements:
                    if syn.lower() in el.text.lower():
                        label_el = el
                        matched_label = syn
                        break
                if label_el is not None:
                    break
            if label_el is None or label_el.bbox is None:
                continue

            label_right = label_el.bbox.x2
            label_y_mid = (label_el.bbox.y1 + label_el.bbox.y2) / 2

            best = None
            best_gap = self.max_gap
            for cand in elements:
                if cand.element_id == label_el.element_id or cand.element_id in used_value_ids:
                    continue
                if cand.page != label_el.page:
                    continue
                if cand.bbox is None:
                    continue
                cand_y_mid = (cand.bbox.y1 + cand.bbox.y2) / 2
                if abs(cand_y_mid - label_y_mid) > self.same_line_tol:
                    continue
                gap = cand.bbox.x1 - label_right
                if 0 < gap < best_gap:
                    best_gap = gap
                    best = cand

            if best is None:
                continue
            used_value_ids.add(best.element_id)
            out.append(
                Candidate(
                    field=fc.name,
                    value=best.text.strip(),
                    confidence=0.82,
                    source=self.name,
                    evidence=Evidence(
                        page=best.page,
                        bbox=best.bbox,
                        element_id=best.element_id,
                        method_detail=f"spatial:{matched_label}",
                    ),
                )
            )
        return out
