# Architecture

## Overview

The Document Parser is a modular pipeline that turns any supported file
(PDF, DOCX, PPTX, XLSX, HTML, image) into structured JSON with field
provenance. Every stage is a swappable plugin behind a Protocol; no stage
assumes a specific document type.

## High-level flow

```
                    POST /api/parse  (any supported file)
                              │
                              ▼
                    ┌─────────────────┐
                    │   FileRouter     │  mime via filetype
                    └────────┬─────────┘
                             ▼
                  ┌───────────────────┐
                  │  DoclingAdapter   │  PRIMARY
                  │  (+ OCR built-in) │
                  └─────────┬─────────┘
                            ▼
                  ┌────────────────────┐
                  │   Quality gate     │  text coverage / table count
                  └─────────┬──────────┘
              augment if needed
            ┌──────────┴───────────┐
            ▼                      ▼
     pdfplumber               pdfminer.six
     (table merge)            (text fallback)
            └──────────┬───────────┘
                       ▼
            ┌───────────────────────┐
            │ Normalized Document   │
            │ (text · elements ·    │
            │  tables · bboxes ·    │
            │  metadata)            │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Schema Discovery      │
            │  heuristic ⊕ GLiNER   │
            │  ⊕ LLM  → consensus   │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Field Extractors      │
            │ regex · keyword ·     │
            │ spatial · table ·     │
            │ NER · LLM             │
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Voting Merger         │
            │ extractor_prior ×     │
            │ confidence × validator│
            └──────────┬────────────┘
                       ▼
            ┌───────────────────────┐
            │ Validators per type   │
            │  date / currency /    │
            │  number / email / id  │
            └──────────┬────────────┘
                       ▼
                Output JSON
```

## Module map

```
server/
├── api/routes.py             # FastAPI: /api/parse, /health
├── core/
│   ├── document.py           # Document, Element, Table, BBox, Candidate, FieldCandidate
│   └── contracts.py          # Protocols: FileAdapter, SchemaDetector, FieldExtractor
├── parser/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── docling_adapter.py
│   │   ├── pdfplumber_adapter.py
│   │   ├── pdfminer_adapter.py
│   │   └── router.py
│   └── input_module.py       # file metadata
├── schema/
│   ├── heuristic_detector.py
│   ├── ner_detector.py       # GLiNER zero-shot
│   ├── llm_detector.py
│   └── consensus.py
├── extractors/
│   ├── regex_extractor.py
│   ├── keyword_extractor.py
│   ├── spatial_extractor.py
│   ├── table_extractor.py
│   ├── ner_extractor.py
│   └── llm_extractor.py
├── validators/__init__.py
├── merge/
│   ├── voting.py
│   └── output_builder.py
├── pipeline.py               # orchestrator
├── eval/
│   ├── fixtures/
│   ├── golden/
│   └── run_eval.py
├── scripts/prewarm.py        # docker-build-time model prewarm
├── api/                      # routes
└── main.py                   # ASGI entrypoint
```

## Stage contracts

```python
class FileAdapter(Protocol):
    name: str
    accepts: set[str]                           # MIME types
    def parse(self, path: str) -> Document: ...

class SchemaDetector(Protocol):
    name: str
    def propose(self, doc: Document) -> list[FieldCandidate]: ...

class FieldExtractor(Protocol):
    name: str
    prior: float
    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]: ...

class Validator(Protocol):
    data_type: str
    def validate(self, value) -> tuple[bool, object]: ...
```

`Document` is the **single boundary type** between parsing and extraction:
swapping any parser does not require changing any extractor, and vice versa.

## Voting merger semantics

For each schema field, every extractor may propose one or more candidates.
For each candidate:

```
score = extractor.prior × candidate.confidence × (1.0 if validator passes else 0.6)
```

Candidates with the same normalized value collapse into a single group whose
score sums (with a small consensus boost). The top-scoring group wins. If a
runner-up group is within 25% of the winner, the field is flagged as
`disagreement`. If the winner's normalized confidence is below
`CONFIDENCE_FLAG_THRESHOLD`, the field is flagged as `low_confidence`.

`evidence` in the output records every contributing extractor (page, bbox,
element id, source quote, method detail) for full audit.

## Output shape

```json
{
  "document": {
    "type": "invoice",
    "parse_method": ["docling", "pdfplumber"],
    "is_scanned": false,
    "metadata": { "filename": "...", "page_count": 1, ... }
  },
  "schema": [
    {"name": "invoice_number", "data_type": "id",
     "detected_by": "heuristic,ner", "confidence": 0.85}
  ],
  "fields": {
    "invoice_number": {
      "value": "INV-001",
      "confidence": 0.92,
      "sources": ["regex", "ner"],
      "agreement_count": 2,
      "validated": true,
      "data_type": "id",
      "evidence": [...],
      "source_quote": null,
      "flags": []
    }
  },
  "flagged_fields": [],
  "tables": [...],
  "elements": [...],
  "elements_truncated": false
}
```

## Extension guide

**Add a new file format**: implement `BaseFileAdapter` in
`server/parser/adapters/`, append it to `FileRouter.adapters`. Done.

**Add a new extractor**: implement `BaseExtractor`, give it a `prior`,
register it in `pipeline._build_extractors()`. The voting merger will pick it
up automatically.

**Add a new schema detector**: implement a class with `name` and `propose()`,
add it to the list in `schema/consensus.py`.

**Add a new data type**: add a `*Validator` to `server/validators/__init__.py`
and a regex pattern to `extractors/regex_extractor.py`.

## Docker

Two-stage Dockerfile:

- Stage 1 builds Python deps with build tools.
- Stage 2 runtime adds Tesseract, poppler-utils, libgl, and runs as a non-root
  user. `RUN python -m server.scripts.prewarm` pre-downloads Docling layout
  weights and the GLiNER checkpoint into `/home/app/.cache/`, so first request
  has no cold start.
- A `model-cache` named volume in `docker-compose.yml` persists those caches
  across container recreations.
- `/health` powers the Docker `HEALTHCHECK`.

```bash
docker compose build
docker compose up -d
curl http://localhost:8000/health
docker compose --profile eval up eval   # run the eval harness
```

## Running locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install tesseract             # or apt-get install tesseract-ocr
cp .env.example .env               # add OPENROUTER_API_KEY if you want LLM
uvicorn server.main:app --reload
```
