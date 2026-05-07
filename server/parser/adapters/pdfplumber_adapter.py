"""pdfplumber adapter — table-focused, used to augment Docling output."""

from __future__ import annotations

import logging
import uuid

from server.core.document import BBox, Document, Page, Table, TableCell, Element
from .base import BaseFileAdapter

log = logging.getLogger(__name__)


class PdfplumberAdapter(BaseFileAdapter):
    name = "pdfplumber"
    accepts = {"application/pdf"}

    def parse(self, path: str) -> Document:
        try:
            import pdfplumber
        except ImportError as e:
            raise ImportError("pdfplumber not installed. `pip install pdfplumber`") from e

        doc = Document(parse_method=["pdfplumber"])

        with pdfplumber.open(path) as pdf:
            for p_idx, page in enumerate(pdf.pages, start=1):
                doc.pages.append(
                    Page(
                        page_no=p_idx,
                        width=float(page.width or 595.28),
                        height=float(page.height or 841.89),
                    )
                )

                # Tables
                try:
                    found = page.find_tables()
                except Exception:
                    found = []

                for ti, t in enumerate(found):
                    tid = f"tbl-p{p_idx}-{ti}-{uuid.uuid4().hex[:6]}"
                    bbox = None
                    try:
                        x0, top, x1, bottom = t.bbox
                        bbox = BBox(x1=float(x0), y1=float(top), x2=float(x1), y2=float(bottom))
                    except Exception:
                        pass

                    extracted = t.extract() or []
                    rows = len(extracted)
                    cols = max((len(r) for r in extracted), default=0)
                    cells: list[TableCell] = []
                    for r_idx, row in enumerate(extracted):
                        for c_idx, cell in enumerate(row):
                            cells.append(
                                TableCell(
                                    row=r_idx,
                                    col=c_idx,
                                    text=(cell or "").strip(),
                                    is_header=(r_idx == 0),
                                )
                            )
                    doc.tables.append(
                        Table(
                            table_id=tid,
                            page=p_idx,
                            bbox=bbox,
                            rows=rows,
                            cols=cols,
                            cells=cells,
                        )
                    )
                    doc.elements.append(
                        Element(
                            element_id=tid,
                            type="table",
                            text="\n".join(c.text for c in cells if c.text),
                            page=p_idx,
                            bbox=bbox,
                        )
                    )

                # Words → fallback elements with bboxes
                try:
                    for w in page.extract_words(use_text_flow=True) or []:
                        bbox = BBox(
                            x1=float(w["x0"]),
                            y1=float(w["top"]),
                            x2=float(w["x1"]),
                            y2=float(w["bottom"]),
                        )
                        doc.elements.append(
                            Element(
                                element_id=f"w-{p_idx}-{uuid.uuid4().hex[:8]}",
                                type="text",
                                text=w["text"],
                                page=p_idx,
                                bbox=bbox,
                            )
                        )
                except Exception as e:
                    log.debug("extract_words failed on page %d: %s", p_idx, e)

                txt = page.extract_text() or ""
                if txt:
                    doc.raw_text += txt + "\n"

        doc.raw_markdown = doc.raw_text  # plain text fallback
        return doc
