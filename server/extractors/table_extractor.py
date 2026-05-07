"""Table extractor — search header cells for field synonyms, return aligned data cell."""

from __future__ import annotations

from server.core.document import Candidate, Document, Evidence, FieldCandidate, Table
from .base import BaseExtractor, synonyms_for


class TableExtractor(BaseExtractor):
    name = "table"
    prior = 0.85

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        if not doc.tables:
            return []
        out: list[Candidate] = []
        for fc in schema:
            for tbl in doc.tables:
                cand = self._extract_from_table(fc, tbl)
                if cand is not None:
                    out.append(cand)
                    break
        return out

    def _extract_from_table(self, fc: FieldCandidate, tbl: Table) -> Candidate | None:
        if not tbl.cells:
            return None
        syns = [s.lower() for s in synonyms_for(fc.name)]
        # find header cell whose text contains a synonym
        for header in tbl.header_row():
            txt = (header.text or "").lower().strip()
            if not txt:
                continue
            if not any(s and s in txt for s in syns):
                continue
            # take the next non-empty cell in the same column
            for c in tbl.cells:
                if c.col == header.col and c.row > header.row and c.text.strip():
                    return Candidate(
                        field=fc.name,
                        value=c.text.strip(),
                        confidence=0.86,
                        source=self.name,
                        evidence=Evidence(
                            page=tbl.page,
                            bbox=c.bbox or tbl.bbox,
                            method_detail=f"table:{tbl.table_id}:col{header.col}",
                        ),
                    )
        return None
