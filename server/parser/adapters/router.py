"""File router with quality gate.

Strategy:
  1. Detect MIME via filetype.
  2. Run the primary adapter that accepts that MIME (Docling).
  3. Quality-gate the result; if tables look thin or text empty, augment
     with pdfplumber (tables) or pdfminer (text fallback).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import filetype

from server.core.document import Document
from .base import BaseFileAdapter
from .docling_adapter import DoclingAdapter
from .pdfminer_adapter import PdfminerAdapter
from .pdfplumber_adapter import PdfplumberAdapter

log = logging.getLogger(__name__)


_EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def detect_mime(path: str) -> str:
    kind = filetype.guess(path)
    if kind:
        return kind.mime
    ext = os.path.splitext(path)[1].lower()
    return _EXT_TO_MIME.get(ext, "application/octet-stream")


class FileRouter:
    def __init__(self, adapters: Optional[list[BaseFileAdapter]] = None):
        self.adapters = adapters or [
            DoclingAdapter(),
        ]
        # secondary parsers for the quality gate (PDF only)
        self._pdfplumber = PdfplumberAdapter()
        self._pdfminer = PdfminerAdapter()

    def _pick(self, mime: str) -> Optional[BaseFileAdapter]:
        for a in self.adapters:
            if mime in a.accepts:
                return a
        return None

    def parse(self, path: str) -> Document:
        mime = detect_mime(path)
        primary = self._pick(mime)
        if primary is None:
            raise ValueError(f"No adapter accepts MIME type: {mime}")

        try:
            doc = primary.parse(path)
        except Exception as e:
            log.warning("primary adapter %s failed: %s — falling back", primary.name, e)
            doc = Document()

        if mime == "application/pdf":
            self._apply_quality_gate(path, doc)

        if not doc.parse_method:
            doc.parse_method = [primary.name]
        return doc

    def _apply_quality_gate(self, path: str, doc: Document) -> None:
        text_len = doc.text_length()
        n_tables = len(doc.tables)

        # Rule 1: if very little text, run pdfminer to recover
        if text_len < 50:
            try:
                pm = self._pdfminer.parse(path)
                if pm.text_length() > text_len:
                    doc.elements.extend(pm.elements)
                    doc.pages = doc.pages or pm.pages
                    doc.raw_text = pm.raw_text or doc.raw_text
                    doc.raw_markdown = pm.raw_markdown or doc.raw_markdown
                    doc.parse_method.append("pdfminer")
            except Exception as e:
                log.warning("pdfminer fallback failed: %s", e)

        # Rule 2: if no tables found and content suggests tabular data, try pdfplumber
        if n_tables == 0 and self._looks_tabular(doc):
            try:
                pp = self._pdfplumber.parse(path)
                if pp.tables:
                    doc.tables.extend(pp.tables)
                    # add table-elements only (avoid blowing up element list with words)
                    doc.elements.extend(e for e in pp.elements if e.type == "table")
                    doc.parse_method.append("pdfplumber")
            except Exception as e:
                log.warning("pdfplumber augmentation failed: %s", e)

    @staticmethod
    def _looks_tabular(doc: Document) -> bool:
        sample = (doc.raw_markdown or doc.raw_text or "")[:4000]
        if not sample:
            return False
        if "|" in sample and sample.count("|") > 4:
            return True
        # heuristic: many lines with multiple consecutive whitespace runs
        lines = sample.splitlines()
        col_lines = sum(1 for ln in lines if "  " in ln.strip() and len(ln.split()) >= 3)
        return col_lines >= 5


_default = FileRouter()


def parse_any(path: str) -> Document:
    return _default.parse(path)
