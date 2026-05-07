# 📄 Document Parser

> A **fully open-source**, format-agnostic document intelligence pipeline that turns any PDF, DOCX, PPTX, XLSX, HTML, or image into structured JSON — with provenance, bounding boxes, and a dynamically discovered schema.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com)
[![Docling](https://img.shields.io/badge/Docling-MIT-orange)](https://github.com/DS4SD/docling)

---

## ✨ Why this exists

Every team eventually needs to extract structured data from messy documents — invoices, contracts, SOWs, reports, scanned forms. Existing solutions force a hard choice:

- **Commercial APIs** (Textract, DocAI, LlamaParse) — accurate, but $$$ and your data leaves the building.
- **Single OSS tools** (just `pdfplumber` or just `unstructured`) — free, but each one is good at *one* thing and mediocre at the rest.
- **Hardcoded rules** — work on day one, break on the next document type.

This project takes a different approach: **combine the best open-source tools behind a clean Protocol-based pipeline, and let them vote.** No single component decides the answer; consensus across regex, layout, NER, and LLM produces auditable, high-confidence output.

> Zero AGPL/GPL/NC dependencies in the runtime tree. Truly self-hostable.

---

## 🎯 Highlights

- 🧩 **Modular pipeline** — every stage is a swappable plugin behind a Protocol.
- 📚 **Format-agnostic intake** — PDF, DOCX, PPTX, XLSX, HTML, Markdown, PNG/JPG/TIFF.
- 🔍 **Dynamic schema discovery** — heuristic + zero-shot NER + LLM ensemble, no hardcoded vocabulary.
- 🗳️ **Voting merger** — six extractors (regex, keyword, spatial, table, NER, LLM) agree on each field.
- 📐 **Provenance everywhere** — page, bbox, element id, source quote per field.
- 🧠 **Outline-aware** — narrative docs (specs, contracts, reports) get a section-level schema for free.
- ⚡ **CPU-only** — no GPU required for the prototype.
- 🐳 **Docker-ready** — one command, models pre-warmed.
- 📜 **Permissive licenses everywhere** — MIT/Apache/MPL only.

---

## 🏗️ Architecture

```
                    POST /api/parse  (any supported file)
                              │
                              ▼
                    ┌─────────────────┐
                    │   FileRouter    │  mime via filetype
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ DoclingAdapter  │  ← PRIMARY (PDF/DOCX/PPTX/XLSX/HTML/IMG + OCR)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Quality Gate   │  text coverage / table count
                    └────────┬────────┘
                augment if needed
            ┌──────────┴───────────┐
            ▼                      ▼
       pdfplumber             pdfminer.six
      (table merge)          (text fallback)
            └──────────┬───────────┘
                       ▼
            ┌───────────────────────┐
            │ Normalized Document   │  text · elements · tables · bboxes · metadata
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Schema Discovery      │
            │  heuristic ⊕ outline  │
            │  ⊕ GLiNER ⊕ LLM →     │
            │  consensus            │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Field Extractors      │  6 in parallel:
            │ regex · keyword ·     │  regex / keyword / spatial /
            │ spatial · table ·     │  table / section / NER / LLM
            │ section · NER · LLM   │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Voting Merger         │  prior × confidence × validator
            │  (consensus boost)    │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Validators per type   │  date · currency · number · email · id
            └──────────┬────────────┘
                       ▼
                  Output JSON
```

📖 See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design, contracts, and extension guide.

---

## 🚀 Quick start

### Option A — Docker (recommended)

```bash
git clone <this-repo>
cd Document-Parser
cp .env.example .env       # edit if you want LLM extraction
docker compose up --build
```

That's it. The image:
- pre-warms Docling layout/table models at build time
- pre-warms GLiNER weights at build time
- exposes `:8000` with a healthcheck
- runs as a non-root user
- persists model caches in a named volume

```bash
curl http://localhost:8000/health
```

Run the eval harness against fixtures:

```bash
docker compose --profile eval up eval
```

### Option B — Local Python

```bash
python -m venv .venv && source .venv/bin/activate

# CPU-only torch first to avoid pulling 6 GB of CUDA wheels
pip install --index-url https://download.pytorch.org/whl/cpu \
            --extra-index-url https://pypi.org/simple \
            torch torchvision

pip install -r requirements.txt
brew install tesseract                   # macOS;  apt-get install tesseract-ocr on Linux

cp .env.example .env                     # optional: add OPENROUTER_API_KEY
python -m uvicorn server.main:app --reload --port 8000
```

> ⚠️ **Use `python -m uvicorn`** — bare `uvicorn` may resolve to your system Python and miss venv packages.

---

## 🔬 Try it

```bash
curl -s -F file=@your_invoice.pdf http://localhost:8000/api/parse | jq '.fields'
```

### Example: invoice (PDF)

```json
{
  "document": {
    "type": "invoice",
    "title": "ACME Corp — Invoice INV-2024-0117",
    "parse_method": ["docling"],
    "is_scanned": false,
    "metadata": { "filename": "invoice.pdf", "page_count": 1, ... }
  },
  "schema": [
    { "name": "invoice_number", "data_type": "id", "detected_by": "heuristic,ner", "confidence": 0.95 },
    { "name": "total",          "data_type": "currency", "detected_by": "heuristic,llm", "confidence": 0.91 },
    { "name": "invoice_date",   "data_type": "date", "detected_by": "heuristic,llm", "confidence": 0.91 }
  ],
  "fields": {
    "invoice_number": {
      "value": "INV-2024-0117",
      "confidence": 0.97,
      "sources": ["regex", "keyword", "ner"],
      "agreement_count": 3,
      "validated": true,
      "evidence": [
        { "source": "regex",   "page": 1, "bbox": {"x1": 410, "y1": 88, "x2": 540, "y2": 104}, "method_detail": "regex:id" },
        { "source": "keyword", "page": 1, "bbox": {...}, "method_detail": "keyword:invoice number" },
        { "source": "ner",     "page": 1, "method_detail": "ner:invoice number", "source_quote": "INV-2024-0117" }
      ]
    },
    "total":        { "value": "$1,234.56", "confidence": 0.93, "sources": ["regex", "table", "llm"], ... },
    "invoice_date": { "value": "2024-01-17", "confidence": 0.92, "validated": true, ... }
  },
  "flagged_fields": [],
  "tables": [...],
  "elements": [...]
}
```

### Example: spec / report (DOCX)

For narrative documents, the **outline detector** kicks in and exposes the section structure as the schema:

```json
{
  "document": {
    "type": "specification",
    "title": "Chat with Your Documents",
    "outline": [
      { "number": "1",    "title": "Introduction",            "page": 1 },
      { "number": "2",    "title": "Problem Statement",       "page": 1 },
      { "number": "3",    "title": "High-Level Flow",         "page": 1 },
      { "number": "5.1",  "title": "Document Chunking",       "page": 1 },
      { "number": "11.2", "title": "README.md",               "page": 1 }
    ]
  },
  "fields": {
    "introduction":      { "value": "This project is a hands-on capstone …", "confidence": 0.85, "sources": ["section"] },
    "problem_statement": { "value": "Large Language Models (LLMs) are powerful but: They do not have access to private documents …", ... },
    "document_chunking": { "value": "Split documents into small chunks. Recommended size: ~400–600 tokens. Optional overlap …", ... }
  }
}
```

---

## 🧠 How dynamic schema discovery works

No vocabulary is hardcoded. Three detectors run in parallel and a **consensus pass** keeps a field when ≥2 detectors agree, *or* one is highly confident.

| Detector | Source | What it finds |
|---|---|---|
| `HeuristicDetector` | regex over text | `Label: Value` pairs, table headers, typed values |
| `OutlineDetector` | element types | Numbered headings → section fields |
| `NerDetector` | GLiNER zero-shot | Entities (person/org/money/date/invoice number/…) |
| `LlmDetector` | Qwen-2.5 via OpenRouter | Document type + free-text field list (optional) |

Synonym normalization handles variants:

```text
invoice_no, inv_no, invoice  → invoice_number
amount_due, grand_total      → total
bill_to, ship_to, customer   → client_name
```

---

## 🗳️ How voting works

For each schema field, every extractor proposes a `Candidate`. The merger scores them:

```
score = extractor_prior × candidate_confidence × validator_pass_multiplier
```

Candidates with the same normalized value collapse into a group whose scores **sum** (consensus boost). The top group wins. If a runner-up group is within 25% of the winner, the field is flagged `disagreement`. Sub-threshold confidence is flagged `low_confidence`.

| Extractor | Prior | Notes |
|---|---|---|
| `regex` | 0.95 | Highest precision on typed values |
| `section` | 0.85 | Aggregates section body into a field |
| `table` | 0.85 | Header-cell aware |
| `llm` | 0.85 | Strong but non-deterministic |
| `spatial` | 0.80 | Bbox geometry, requires reliable layout |
| `keyword` | 0.75 | Brittle on multi-column |
| `ner` | 0.70 | Generalizes broadly |

---

## 🧰 Open-source stack

Every dependency is permissive (MIT / Apache / MPL):

| Layer | Tool | License |
|---|---|---|
| Primary parser | [Docling](https://github.com/DS4SD/docling) | MIT |
| Table augmenter | [pdfplumber](https://github.com/jsvine/pdfplumber) | MIT |
| Text fallback | [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | MIT |
| OCR | [Tesseract](https://github.com/tesseract-ocr/tesseract) (via Docling) | Apache-2.0 |
| Zero-shot NER | [GLiNER](https://github.com/urchade/GLiNER) | Apache-2.0 |
| LLM client | [instructor](https://github.com/jxnl/instructor) + OpenRouter | Apache-2.0 |
| Type validation | [Pydantic](https://github.com/pydantic/pydantic) | MIT |
| HTTP API | [FastAPI](https://github.com/tiangolo/fastapi) | MIT |
| Date parsing | [python-dateutil](https://github.com/dateutil/dateutil) | Apache-2.0 |

📖 See [`docs/RESEARCH.md`](docs/RESEARCH.md) for the full landscape comparison and licensing analysis.

---

## ⚙️ Configuration

All config is via environment variables. Copy `.env.example` to `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | empty | Enables LLM stage. Leave blank to run fully offline. |
| `LLM_SCHEMA_MODEL` | `qwen/qwen-2.5-7b-instruct` | Cheap model for schema detection |
| `LLM_EXTRACT_MODEL` | `qwen/qwen3-30b-a3b` | Bigger model for value extraction |
| `ENABLE_NER` | `1` | Set `0` to skip GLiNER (saves ~1 GB cache) |
| `ENABLE_LLM` | `1` | Set `0` to bypass LLM stages |
| `GLINER_MODEL` | `urchade/gliner_multi-v2.1` | HuggingFace model id |
| `CONFIDENCE_FLAG_THRESHOLD` | `0.6` | Below → field is flagged for review |
| `CORS_ORIGINS` | `*` | Comma-separated origins |
| `MAX_UPLOAD_BYTES` | `52428800` | 50 MiB upload cap |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose tracing |

### Profile presets

**Fully offline (no LLM, no NER):**
```bash
ENABLE_LLM=0
ENABLE_NER=0
```

**LLM-only mode (skip NER for faster startup):**
```bash
ENABLE_NER=0
OPENROUTER_API_KEY=sk-or-v1-...
```

**Full ensemble (recommended):**
```bash
ENABLE_NER=1
ENABLE_LLM=1
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## 🌐 API

### `POST /api/parse`

Multipart upload. Returns the structured JSON shape shown above.

```bash
curl -s -F file=@document.pdf http://localhost:8000/api/parse
```

Limits:
- `MAX_UPLOAD_BYTES` (default 50 MiB)
- Heavy work runs in `asyncio.to_thread`, so the event loop stays free
- First request to a cold container downloads models; subsequent are fast

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "parsers": ["docling", "pdfplumber", "pdfminer"],
  "extractors": ["regex", "keyword", "spatial", "table", "section", "ner", "llm"],
  "schema_detectors": ["heuristic", "outline", "ner", "llm"]
}
```

---

## 📁 Project structure

```
.
├── server/
│   ├── api/routes.py                FastAPI: /api/parse, /health
│   ├── core/
│   │   ├── document.py              Document, Element, Table, BBox, Candidate
│   │   ├── contracts.py             Protocols: FileAdapter, SchemaDetector, FieldExtractor
│   │   └── registry.py              Plugin registry
│   ├── parser/
│   │   ├── adapters/
│   │   │   ├── docling_adapter.py   PRIMARY
│   │   │   ├── pdfplumber_adapter.py
│   │   │   ├── pdfminer_adapter.py
│   │   │   └── router.py            mime → adapter, runs quality gate
│   │   └── input_module.py          File metadata
│   ├── schema/
│   │   ├── heuristic_detector.py
│   │   ├── outline_detector.py      Numbered headings → fields
│   │   ├── ner_detector.py          GLiNER zero-shot
│   │   ├── llm_detector.py
│   │   └── consensus.py
│   ├── extractors/
│   │   ├── regex_extractor.py
│   │   ├── keyword_extractor.py
│   │   ├── spatial_extractor.py
│   │   ├── table_extractor.py
│   │   ├── section_extractor.py     Section body extraction
│   │   ├── ner_extractor.py
│   │   └── llm_extractor.py
│   ├── validators/                  Per data-type
│   ├── merge/
│   │   ├── voting.py                Confidence-weighted vote
│   │   └── output_builder.py
│   ├── pipeline.py                  Orchestrator
│   ├── eval/
│   │   ├── fixtures/
│   │   ├── golden/
│   │   └── run_eval.py              F1 metrics per fixture
│   ├── scripts/prewarm.py           Docker-build-time model warmup
│   └── main.py                      ASGI entrypoint
├── docs/
│   ├── RESEARCH.md                  Tool comparison + license matrix
│   ├── ARCHITECTURE.md              Diagram + contracts + extension guide
│   └── OBSERVATIONS.md              Limits, priors, verification steps
├── Dockerfile                       Multi-stage CPU-only image
├── docker-compose.yml               api + eval profile
├── .env.example
├── requirements.txt
└── test_pipeline.py                 Smoke tests
```

---

## 🧪 Eval harness

Drop a fixture into `server/eval/fixtures/<name>.<ext>` and create `server/eval/golden/<name>.json`:

```json
{
  "expected_doc_type": "invoice",
  "fields": {
    "invoice_number": "INV-2024-001",
    "total": "$1,234.56",
    "invoice_date": "2024-01-10"
  }
}
```

Run:

```bash
python -m server.eval.run_eval --out server/eval/results.json
```

Output is per-fixture precision/recall/F1 with extractor source attribution — drives both confidence-prior calibration and the empirical section of `docs/OBSERVATIONS.md`.

---

## 🧩 Extending the pipeline

**Add a new file format** — implement `BaseFileAdapter`:

```python
from server.parser.adapters.base import BaseFileAdapter
from server.core.document import Document

class MyAdapter(BaseFileAdapter):
    name = "mine"
    accepts = {"application/x-mine"}
    def parse(self, path: str) -> Document: ...
```

Append it to `FileRouter.adapters`. Done.

**Add a new extractor** — implement `BaseExtractor` with a `prior`:

```python
from server.extractors.base import BaseExtractor

class MyExtractor(BaseExtractor):
    name = "mine"
    prior = 0.7
    def extract(self, doc, schema): ...
```

Add it to `pipeline._build_extractors()`. The voting merger picks it up automatically.

**Add a new schema detector** — implement `name` + `propose(doc) -> list[FieldCandidate]` and add it to `schema/consensus.py`.

📖 Full extension guide in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 🗺️ Roadmap

- [ ] Legacy `.doc` / `.rtf` / `.eml` / `.msg` adapters (subprocess-isolated)
- [ ] docTR adapter as higher-quality OCR fallback
- [ ] Schema registry — known templates as priors
- [ ] LayoutLMv3 / Donut re-ranker for low-confidence fields
- [ ] Streaming per-page parsing for >200 page documents
- [ ] Human-in-the-loop feedback endpoint → grow golden set
- [ ] Per-tenant schema overrides
- [ ] Local LLM via vLLM/Ollama for fully-air-gapped deployments

---

## 📊 Limitations

- Docling first-run downloads ~hundreds of MB of layout/table model weights. Use the Docker prewarm or `python -m server.scripts.prewarm` to avoid cold-start latency.
- GLiNER weights are ~1.16 GB. Set `ENABLE_NER=0` to skip.
- Borderless tables are still tricky for any OSS extractor.
- Voting priors are seeded from intuition — calibrate from `run_eval.py` results on your corpus.
- LLM extraction quality depends on the chosen model; default Qwen-2.5/3 are a strong cost/quality compromise.

📖 See [`docs/OBSERVATIONS.md`](docs/OBSERVATIONS.md) for the full known-limits log.

---

## 🤝 Contributing

PRs welcome. The design intentionally keeps each layer small and Protocol-bound so adding a parser/extractor/detector is one file.

```bash
# Run smoke tests
python test_pipeline.py

# Run eval harness
python -m server.eval.run_eval

# Lint
python -m compileall server/
```

---

## 📜 License

MIT — see [`LICENSE`](LICENSE).

This project's runtime tree is intentionally free of AGPL/GPL/NC dependencies. Subprocess-only system tools (e.g. `poppler-utils`) are not statically linked and don't propagate copyleft.

---

## 🙏 Credits

Built on the shoulders of giants:

- [**IBM Docling**](https://github.com/DS4SD/docling) — the parser that made multi-format intake possible without API keys.
- [**Urchade Zaratiana / GLiNER**](https://github.com/urchade/GLiNER) — zero-shot NER that fits the "generic schema" goal perfectly.
- [**Jason Liu / instructor**](https://github.com/jxnl/instructor) — typed LLM output without the boilerplate.
- The [**pdfplumber**](https://github.com/jsvine/pdfplumber) and [**pdfminer.six**](https://github.com/pdfminer/pdfminer.six) maintainers — pure-Python PDF extraction that just works.

---

<p align="center">
  <em>If this saves you a week of plumbing, give it a star ⭐</em>
</p>
