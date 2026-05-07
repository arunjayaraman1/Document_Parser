"""Pre-download Docling and GLiNER weights at image build time.

Run with:
    python -m server.scripts.prewarm
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("prewarm")


def warm_docling():
    log.info("→ warming Docling models (layout + tables)…")
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except Exception as e:
        log.warning("docling import failed: %s", e)
        return False
    try:
        opts = PdfPipelineOptions()
        opts.do_ocr = True
        opts.do_table_structure = True
        DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
        log.info("  ✓ docling pipeline initialized")
        return True
    except Exception as e:
        log.warning("docling warmup failed: %s", e)
        return False


def warm_gliner():
    if os.getenv("ENABLE_NER", "1") != "1":
        log.info("→ skipping GLiNER (ENABLE_NER=0)")
        return True
    name = os.getenv("GLINER_MODEL", "urchade/gliner_multi-v2.1")
    log.info("→ warming GLiNER model %s…", name)
    try:
        from gliner import GLiNER
    except Exception as e:
        log.warning("gliner import failed: %s", e)
        return False
    try:
        GLiNER.from_pretrained(name)
        log.info("  ✓ GLiNER weights cached")
        return True
    except Exception as e:
        log.warning("gliner warmup failed: %s", e)
        return False


def main():
    ok = True
    ok &= warm_docling()
    ok &= warm_gliner()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
