"""FastAPI routes."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from server.pipeline import process_document

log = logging.getLogger(__name__)

router = APIRouter()


_MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50 MiB default


@router.get("/")
def root():
    return {
        "service": "document-parser",
        "endpoints": ["/api/parse", "/health"],
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "parsers": ["docling", "pdfplumber", "pdfminer"],
        "extractors": ["regex", "keyword", "spatial", "table", "ner", "llm"],
        "schema_detectors": ["heuristic", "ner", "llm"],
    }


@router.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """Parse a document and extract structured data.

    Accepts PDF / DOCX / PPTX / XLSX / HTML / Markdown / images.
    Returns JSON with discovered schema, extracted fields with provenance,
    tables, document elements with bboxes, and flagged fields.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")

    ext = os.path.splitext(file.filename)[1] or ".bin"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large ({_MAX_BYTES} byte cap)")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Heavy work runs off the event loop
        result = await asyncio.to_thread(process_document, tmp_path)
        return result
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
