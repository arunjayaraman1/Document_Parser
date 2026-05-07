"""Docling adapter (PRIMARY) — handles PDF/DOCX/PPTX/XLSX/HTML/Images with built-in OCR."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from server.core.document import (
    BBox,
    Document,
    Element,
    ElementType,
    Page,
    Table,
    TableCell,
)
from .base import BaseFileAdapter

log = logging.getLogger(__name__)


_LABEL_TO_TYPE: dict[str, ElementType] = {
    "title": "title",
    "section_header": "heading",
    "paragraph": "paragraph",
    "text": "paragraph",
    "list_item": "list_item",
    "table": "table",
    "picture": "figure",
    "caption": "caption",
    "page_header": "header",
    "page_footer": "footer",
    "footnote": "footnote",
}


def _norm_type(label: str) -> ElementType:
    return _LABEL_TO_TYPE.get((label or "").lower(), "text")


def _bbox_from_prov(prov) -> BBox | None:
    """Docling provenance objects expose bbox via .bbox with l/t/r/b or x0/y0/x1/y1."""
    try:
        b = getattr(prov, "bbox", None)
        if b is None:
            return None
        l = getattr(b, "l", None) or getattr(b, "x0", None)
        t = getattr(b, "t", None) or getattr(b, "y0", None)
        r = getattr(b, "r", None) or getattr(b, "x1", None)
        bo = getattr(b, "b", None) or getattr(b, "y1", None)
        if None in (l, t, r, bo):
            return None
        return BBox(x1=float(l), y1=float(t), x2=float(r), y2=float(bo))
    except Exception:
        return None


class DoclingAdapter(BaseFileAdapter):
    name = "docling"
    accepts = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
        "text/markdown",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }

    def __init__(self, ocr: bool = True, table_structure: bool = True):
        self.ocr = ocr
        self.table_structure = table_structure
        self._converter = None  # lazy

    def _get_converter(self):
        if self._converter is not None:
            return self._converter
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
        except ImportError as e:
            raise ImportError(
                "docling is not installed. `pip install docling`."
            ) from e

        pipeline = PdfPipelineOptions()
        pipeline.do_ocr = self.ocr
        pipeline.do_table_structure = self.table_structure

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
            }
        )
        return self._converter

    def parse(self, path: str) -> Document:
        converter = self._get_converter()
        result = converter.convert(path)
        dl = result.document  # DoclingDocument

        doc = Document(parse_method=["docling"])

        # Pages
        try:
            for p in getattr(dl, "pages", {}).values():
                doc.pages.append(
                    Page(
                        page_no=getattr(p, "page_no", 1),
                        width=float(getattr(getattr(p, "size", None), "width", 595.28) or 595.28),
                        height=float(getattr(getattr(p, "size", None), "height", 841.89) or 841.89),
                    )
                )
        except Exception as e:
            log.debug("docling pages walk failed: %s", e)

        # Elements (texts + headings + lists)
        try:
            for it in getattr(dl, "texts", []):
                el_id = getattr(it, "self_ref", None) or f"el-{uuid.uuid4().hex[:8]}"
                label = getattr(it, "label", None)
                label_str = getattr(label, "value", None) if label is not None else None
                el_type = _norm_type(label_str or "text")
                provs = getattr(it, "prov", []) or []
                page = getattr(provs[0], "page_no", 1) if provs else 1
                bbox = _bbox_from_prov(provs[0]) if provs else None
                doc.elements.append(
                    Element(
                        element_id=str(el_id),
                        type=el_type,
                        text=getattr(it, "text", "") or "",
                        page=int(page),
                        bbox=bbox,
                    )
                )
        except Exception as e:
            log.warning("docling text walk failed: %s", e)

        # Tables
        try:
            for ti, t in enumerate(getattr(dl, "tables", []) or []):
                tid = getattr(t, "self_ref", None) or f"tbl-{ti}"
                provs = getattr(t, "prov", []) or []
                page = int(getattr(provs[0], "page_no", 1)) if provs else 1
                bbox = _bbox_from_prov(provs[0]) if provs else None

                cells: list[TableCell] = []
                rows = cols = 0
                data = getattr(t, "data", None)
                if data is not None:
                    grid = getattr(data, "grid", None) or []
                    rows = len(grid)
                    cols = max((len(r) for r in grid), default=0)
                    for r_idx, row in enumerate(grid):
                        for c_idx, cell in enumerate(row):
                            text = getattr(cell, "text", "") or ""
                            is_header = bool(
                                getattr(cell, "column_header", False)
                                or getattr(cell, "row_header", False)
                            )
                            cells.append(
                                TableCell(
                                    row=r_idx,
                                    col=c_idx,
                                    text=text,
                                    is_header=is_header,
                                    rowspan=int(getattr(cell, "row_span", 1) or 1),
                                    colspan=int(getattr(cell, "col_span", 1) or 1),
                                )
                            )
                doc.tables.append(
                    Table(
                        table_id=str(tid),
                        page=page,
                        bbox=bbox,
                        rows=rows,
                        cols=cols,
                        cells=cells,
                    )
                )
                # Also expose tables as elements for spatial ops
                doc.elements.append(
                    Element(
                        element_id=str(tid),
                        type="table",
                        text="\n".join(c.text for c in cells if c.text),
                        page=page,
                        bbox=bbox,
                    )
                )
        except Exception as e:
            log.warning("docling table walk failed: %s", e)

        # Markdown + plaintext
        try:
            doc.raw_markdown = dl.export_to_markdown()
        except Exception as e:
            log.debug("export_to_markdown failed: %s", e)
            doc.raw_markdown = ""
        doc.raw_text = doc.raw_markdown or "\n".join(e.text for e in doc.elements if e.text)

        # OCR usage hint
        try:
            if self.ocr and any(getattr(p, "is_ocr", False) for p in getattr(dl, "pages", {}).values()):
                doc.parse_method.append("ocr")
        except Exception:
            pass

        return doc
