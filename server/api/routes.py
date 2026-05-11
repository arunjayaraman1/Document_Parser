"""FastAPI routes."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from server.parser.adapters.docling_adapter import DoclingAdapter
from server.parser.adapters.pdfminer_adapter import PdfminerAdapter
from server.parser.adapters.pdfplumber_adapter import PdfplumberAdapter
from server.parser.adapters.router import detect_mime
from server.pipeline import process_document

log = logging.getLogger(__name__)

router = APIRouter()


_MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50 MiB default

# Module-level adapter singletons.  Heavy state (Docling's DocumentConverter +
# layout/table model weights) is cached after the first call, so repeated
# requests are fast.
_docling = DoclingAdapter()
_pdfplumber = PdfplumberAdapter()
_pdfminer = PdfminerAdapter()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _save_upload(file: UploadFile) -> Path:
    """Validate an upload and persist it to a tempfile. Returns the temp path."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    ext = os.path.splitext(file.filename)[1] or ".bin"
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="empty file")
    if len(body) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large ({_MAX_BYTES} byte cap)")
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(body)
    finally:
        tmp.close()
    return Path(tmp.name)


def _require_pdf(path: Path) -> None:
    """Reject the request if the file isn't a PDF (by magic-byte detection)."""
    if detect_mime(str(path)) != "application/pdf":
        raise HTTPException(status_code=415, detail="this endpoint only accepts PDF files")


async def _run_adapter(adapter, path: Path) -> dict:
    """Invoke a parser adapter off the event loop and return its Document as dict."""
    try:
        doc = await asyncio.to_thread(adapter.parse, str(path))
        return doc.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%s parse failed", getattr(adapter, "name", "adapter"))
        raise HTTPException(
            status_code=500,
            detail=f"{getattr(adapter, 'name', 'adapter')} parse failed: {e}",
        )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/")
def root():
    return {
        "service": "document-parser",
        "endpoints": [
            "/api/parse",
            "/api/parse/docling",
            "/api/parse/pdfplumber",
            "/api/parse/pdfminer",
            "/health",
        ],
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "parsers": ["docling", "pdfplumber", "pdfminer"],
        "extractors": ["regex", "keyword", "spatial", "table", "table_kv", "section", "ner", "llm"],
        "schema_detectors": ["heuristic", "outline", "ner", "llm"],
        "debug_endpoints": [
            "/api/parse/docling",
            "/api/parse/pdfplumber",
            "/api/parse/pdfminer",
        ],
    }


@router.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """Full pipeline: parse → schema discovery → extract → vote → output.

    Accepts PDF / DOCX / PPTX / XLSX / HTML / Markdown / images.
    Returns JSON with discovered schema, extracted fields with provenance,
    tables, document elements with bboxes, and flagged fields.
    """
    path = await _save_upload(file)
    try:
        return await asyncio.to_thread(process_document, str(path))
    finally:
        path.unlink(missing_ok=True)


# ── Debug endpoints — one parser, no downstream pipeline ─────────────────────


@router.post("/api/parse/docling")
async def parse_with_docling(file: UploadFile = File(...)):
    """Run **Docling alone**. Multi-format (PDF/DOCX/PPTX/XLSX/HTML/IMG).

    No quality gate, no schema discovery, no extractors, no voting.
    Returns the raw normalized `Document`: pages, elements, tables,
    raw_markdown, raw_text, metadata, parse_method.
    """
    path = await _save_upload(file)
    try:
        return await _run_adapter(_docling, path)
    finally:
        path.unlink(missing_ok=True)


@router.post("/api/parse/pdfplumber")
async def parse_with_pdfplumber(file: UploadFile = File(...)):
    """Run **pdfplumber alone** (PDF only). Strong on tables and word-level bboxes."""
    path = await _save_upload(file)
    try:
        _require_pdf(path)
        return await _run_adapter(_pdfplumber, path)
    finally:
        path.unlink(missing_ok=True)


@router.post("/api/parse/pdfminer")
async def parse_with_pdfminer(file: UploadFile = File(...)):
    """Run **pdfminer.six alone** (PDF only). Pure-Python text extraction fallback."""
    path = await _save_upload(file)
    try:
        _require_pdf(path)
        return await _run_adapter(_pdfminer, path)
    finally:
        path.unlink(missing_ok=True)
