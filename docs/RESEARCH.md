# Research Summary

This document captures the open-source landscape considered when designing the
generic document parser, and explains the choices the system makes.

## 1. Open-source PDF parsers

| Tool | License | Born-digital text | Tables | Layout / reading order | OCR | Multi-format | Notes |
|---|---|:-:|:-:|:-:|:-:|:-:|---|
| **Docling** (IBM) | **MIT** | ✅ | ✅ | ✅ | ✅ (Tesseract / EasyOCR) | ✅ PDF/DOCX/PPTX/XLSX/HTML/IMG | Picked as **primary** — single API, full coverage, permissive weights |
| **Unstructured (lib)** | Apache-2.0 | ⚠ | ⚠ | ✅ | via Tesseract | ✅ | Good element typing; heavy deps; weaker tables than Docling |
| **pdfplumber** | MIT | ✅ | ✅ | ❌ | ❌ | ❌ | Best OSS table extractor — kept as table augmenter |
| **pdfminer.six** | MIT | ✅ | ❌ | ⚠ | ❌ | ❌ | Pure-Python text fallback |
| **PyMuPDF (fitz)** | **AGPL-3.0** | ✅ | ❌ | ⚠ | ❌ | ⚠ | Fast, but AGPL contaminates closed services — **excluded** |
| **Camelot** | MIT (depends on Ghostscript **AGPL**) | ❌ | ✅ | ❌ | ❌ | ❌ | Ghostscript dep → excluded |
| **Marker** | **GPL-3.0** | ✅ | ✅ | ✅ | ✅ | ⚠ | Excellent quality, but GPL — excluded |
| **MinerU** | **AGPL-3.0** | ✅ | ✅ | ✅ | ✅ | ⚠ | AGPL — excluded |
| **Surya** | **GPL-3.0** | ⚠ | ✅ | ✅ | ✅ | ⚠ | GPL — excluded |
| **PaddleOCR** | Apache-2.0 (mixed model licenses) | ❌ | ⚠ | ⚠ | ✅ | ⚠ | Some checkpoints unclear — not a primary choice |
| **EasyOCR** | Apache-2.0 (some NC models) | ❌ | ❌ | ❌ | ✅ | ❌ | NC checkpoint risk |
| **docTR** | Apache-2.0 (code + weights) | ❌ | ❌ | ✅ | ✅ | ❌ | Strong OCR alternative if Tesseract is too weak |
| **Tesseract** | Apache-2.0 | ❌ | ❌ | ❌ | ✅ | ❌ | Backbone OCR; bundled by Docling |
| **OCRmyPDF** | MPL-2.0 | ❌ | ❌ | ❌ | ✅ | ❌ | Useful as a separate "reinject text layer" pre-step |

**Conclusion:** Docling is the only **fully permissive** modern doc-AI parser
that handles PDFs, Office docs, HTML and images in one API. We pair it with
**pdfplumber** for table augmentation and **pdfminer.six** as a pure-Python
text-only fallback. All three are MIT.

## 2. Information extraction techniques

| Technique | Strength | Weakness | Used in this system |
|---|---|---|---|
| **Regex / heuristics** | Perfect precision on typed values (date, money, email, phone, percentage) | Brittle on unseen layouts; type-only | `extractors/regex_extractor.py` — patterns keyed on `data_type` |
| **Keyword / label proximity** | Works for "Label: Value" forms | Multi-column / tables defeat it | `extractors/keyword_extractor.py` — vocabulary derived from the **discovered** schema, not hardcoded |
| **Spatial / layout** | Handles forms with bbox geometry | Needs reliable bboxes | `extractors/spatial_extractor.py` |
| **Table-aware extraction** | Required for invoices / reports / SOWs with line items | Misses borderless tables | `extractors/table_extractor.py` |
| **NER (spaCy / GLiNER)** | Generalizes across documents | Mediocre on proprietary IDs | `extractors/ner_extractor.py` — **GLiNER zero-shot** so labels match the discovered schema |
| **LLMs (Qwen / Llama / Claude)** | Best on messy / contextual docs | Expensive; non-deterministic | `extractors/llm_extractor.py` (2-stage; existing `instructor` + OpenRouter pipeline) |

We run **all six** in parallel and merge with confidence-weighted voting
(`merge/voting.py`). No single technique decides a field.

## 3. Schema-extraction approaches

| Approach | Pros | Cons | Used? |
|---|---|---|---|
| Heuristic (KV pairs, table headers) | No external deps, deterministic | Misses free-text fields | ✅ `schema/heuristic_detector.py` |
| Zero-shot NER (GLiNER) | Generalizes to any domain via label prompts | Latency, model size | ✅ `schema/ner_detector.py` |
| LLM schema detection | Flexible, semantic | Cost, non-determinism, requires API | ✅ `schema/llm_detector.py` (optional) |
| Template / registry of known schemas | Fast on repeat docs | Cold-start, maintenance | (planned, future work) |
| Layout/template clustering | Learns from distribution | Needs labeled corpus | (future work) |

We run heuristic + NER + LLM, then a **consensus pass**
(`schema/consensus.py`) keeps a field when ≥2 detectors agree, or one is highly
confident. This makes schema discovery genuinely dynamic — no fallback to a
hardcoded invoice/SOW vocabulary.

## 4. Existing open-source pipelines reviewed

| Project | What we borrowed |
|---|---|
| **Docling** | Stage-based pipeline, normalized DoclingDocument model |
| **Unstructured** | Notion of semantic element types (heading/list/table) |
| **Haystack DocumentLoaders** | Adapter Protocol pattern across formats |
| **deepdoctection** | Multi-tool orchestration (object detection + OCR + layout) |
| **LlamaIndex / LlamaParse (commercial, for design only)** | Two-stage schema-then-extract LLM pattern |

## 5. Licensing posture

**Goal:** zero AGPL / GPL / NC packages in the runtime tree.

| Package | License |
|---|---|
| docling | MIT |
| pdfplumber | MIT |
| pdfminer.six | MIT |
| Tesseract (system pkg) | Apache-2.0 |
| python-docx, openpyxl, python-pptx | MIT |
| trafilatura | Apache-2.0 |
| GLiNER (`gliner_multi-v2.1`) | Apache-2.0 (code + weights) |
| instructor, openai SDK | Apache-2.0 / Apache-2.0 |
| FastAPI / Pydantic / uvicorn | MIT / MIT / BSD |

`poppler-utils` is GPL-2.0+ but is invoked as a **subprocess** by Docling /
pdfplumber rather than linked into our process — subprocess invocation does
not create a derivative work, so the service stays clean.

## 6. Limitations & known gaps

- Legacy `.doc`, `.rtf`, `.eml`, `.msg` formats are not yet supported. (Future
  work: subprocess to LibreOffice / `mail-parser`.)
- Scanned multi-column reports may still degrade on CPU — consider adding
  `docTR` adapter or running Docling with EasyOCR.
- Voting priors (`extractor.prior`) are seeded from intuition; should be
  recalibrated from eval-harness output once a real corpus exists.
- LLM stage is bound to OpenRouter; for fully offline operation, replace with a
  local vLLM/Ollama endpoint that exposes an OpenAI-compatible API.
