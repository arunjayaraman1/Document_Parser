"""pdfminer.six adapter — pure-Python text+bbox fallback."""

from __future__ import annotations

import logging
import uuid

from server.core.document import BBox, Document, Element, Page
from .base import BaseFileAdapter

log = logging.getLogger(__name__)


class PdfminerAdapter(BaseFileAdapter):
    name = "pdfminer"
    accepts = {"application/pdf"}

    def parse(self, path: str) -> Document:
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LTTextContainer, LTTextLine, LTPage
        except ImportError as e:
            raise ImportError("pdfminer.six not installed. `pip install pdfminer.six`") from e

        doc = Document(parse_method=["pdfminer"])
        text_chunks: list[str] = []

        for page_layout in extract_pages(path):
            if not isinstance(page_layout, LTPage):
                continue
            p_no = page_layout.pageid
            doc.pages.append(
                Page(page_no=int(p_no), width=float(page_layout.width), height=float(page_layout.height))
            )
            for elem in page_layout:
                if isinstance(elem, LTTextContainer):
                    for line in elem:
                        if isinstance(line, LTTextLine):
                            text = line.get_text().strip()
                            if not text:
                                continue
                            x0, y0, x1, y1 = line.bbox
                            # pdfminer y origin is bottom-left; flip to top-left
                            page_h = page_layout.height
                            bbox = BBox(
                                x1=float(x0),
                                y1=float(page_h - y1),
                                x2=float(x1),
                                y2=float(page_h - y0),
                            )
                            doc.elements.append(
                                Element(
                                    element_id=f"pm-{p_no}-{uuid.uuid4().hex[:8]}",
                                    type="text",
                                    text=text,
                                    page=int(p_no),
                                    bbox=bbox,
                                )
                            )
                            text_chunks.append(text)

        doc.raw_text = "\n".join(text_chunks)
        doc.raw_markdown = doc.raw_text
        return doc
