"""Table Key/Value extractor — handles vertical label/value strips in tables.

Complements `TableExtractor` (which does column-aligned header → first-data-cell)
by handling the dominant pattern in invoices/receipts/quotes where labels and
their values appear on different rows of a table:

    | Subtotal:       |         |   ← label row
    |                 | $48.71  |   ← value row, +1
    | Discount (20%): | $9.74   |   ← same-row pair
    | Shipping:       |         |
    |                 | $11.13  |
    | Total:          |         |
    |                 | $50.10  |

Algorithm
---------
1.  Identify *line-item rows* (col 0 non-empty) and exclude their cells.
2.  Collect *label cells*: text ending with ':', not in col 0.
3.  Collect *value cells*: currency / number / percentage cells on
    non-line-item rows.
4.  Greedy assign each label to the nearest unused value cell within
    `max_row_distance` rows and same-or-rightward column.
"""

from __future__ import annotations

import re

from server.core.document import Candidate, Document, Evidence, FieldCandidate, Table, TableCell
from .base import BaseExtractor

_CURRENCY_RE = re.compile(r"^\s*(?:\$|€|£|¥|USD|EUR|GBP|INR)\s*[\d,]+(?:\.\d{1,2})?\s*$", re.I)
_NUMBER_RE = re.compile(r"^\s*-?[\d,]+(?:\.\d+)?\s*$")
_PERCENT_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*%\s*$")


def _looks_like_value(text: str) -> str | None:
    """Return inferred data_type if `text` looks like a value, else None."""
    t = text.strip()
    if not t:
        return None
    if _CURRENCY_RE.match(t):
        return "currency"
    if _PERCENT_RE.match(t):
        return "percentage"
    if _NUMBER_RE.match(t):
        return "number"
    return None


def _normalize_label(text: str) -> str:
    """`Discount (20%):` → `discount`."""
    t = text.rstrip(":").strip()
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t)
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower()
    return t


class TableKVExtractor(BaseExtractor):
    name = "table_kv"
    prior = 0.85
    max_row_distance = 2
    max_col_offset = 2

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]:
        out: list[Candidate] = []
        for tbl in doc.tables:
            out.extend(self._from_table(tbl))
        return out

    def _from_table(self, tbl: Table) -> list[Candidate]:
        if not tbl.cells:
            return []
        cells = {(c.row, c.col): c for c in tbl.cells}

        # Rows where col-0 is non-empty are line-item rows; their values are
        # *not* part of a vertical financial strip.
        line_item_rows = {
            c.row for c in tbl.cells if c.col == 0 and c.text.strip()
        }

        # Labels: text ends with ':', not in col 0 (col-0 labels tend to be
        # item descriptions, not financial labels).
        labels: list[TableCell] = sorted(
            (c for c in tbl.cells
             if c.text.strip().endswith(":") and c.col > 0),
            key=lambda x: (x.row, x.col),
        )
        if not labels:
            return []

        # Values: currency / number / percent cells on non-line-item rows.
        value_pool: dict[tuple[int, int], tuple[TableCell, str]] = {}
        for (r, col), c in cells.items():
            if r in line_item_rows:
                continue
            dtype = _looks_like_value(c.text)
            if dtype is None:
                continue
            value_pool[(r, col)] = (c, dtype)
        if not value_pool:
            return []

        used: set[tuple[int, int]] = set()
        out: list[Candidate] = []

        for label in labels:
            target_col = label.col + 1
            best: tuple[int, tuple[int, int], TableCell, str] | None = None
            for (vr, vc), (vcell, dtype) in value_pool.items():
                if (vr, vc) in used:
                    continue
                col_off = vc - target_col
                if col_off < 0 or col_off > self.max_col_offset:
                    continue
                row_dist = abs(vr - label.row)
                if row_dist > self.max_row_distance:
                    continue
                # Row distance dominates; same-row pairs win, then nearest neighbours.
                score = row_dist * 10 + col_off
                if best is None or score < best[0]:
                    best = (score, (vr, vc), vcell, dtype)

            if best is None:
                continue
            _, key, vcell, dtype = best
            used.add(key)

            field_name = _normalize_label(label.text)
            if not field_name:
                continue

            out.append(
                Candidate(
                    field=field_name,
                    value=vcell.text.strip(),
                    confidence=0.86,
                    source=self.name,
                    evidence=Evidence(
                        page=tbl.page,
                        bbox=vcell.bbox or tbl.bbox,
                        element_id=tbl.table_id,
                        source_quote=f"{label.text.strip()} {vcell.text.strip()}",
                        method_detail=(
                            f"table_kv:{tbl.table_id}:"
                            f"r{label.row}c{label.col}->r{vcell.row}c{vcell.col}"
                        ),
                    ),
                )
            )
        return out
