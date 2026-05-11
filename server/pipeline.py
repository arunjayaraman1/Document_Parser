"""End-to-end pipeline: router → schema discovery → extractors → voting → output."""

from __future__ import annotations

import logging
import os

from server.core.document import Document
from server.merge.output_builder import build_output
from server.merge.voting import vote
from server.parser.adapters.router import parse_any
from server.parser.input_module import extract_file_metadata
from server.schema.consensus import detect_schema as discover_schema

log = logging.getLogger(__name__)


def _build_extractors():
    from server.extractors.regex_extractor import RegexExtractor
    from server.extractors.keyword_extractor import KeywordExtractor
    from server.extractors.spatial_extractor import SpatialExtractor
    from server.extractors.table_extractor import TableExtractor
    from server.extractors.table_kv_extractor import TableKVExtractor
    from server.extractors.section_extractor import SectionExtractor
    from server.extractors.ner_extractor import NerExtractor
    from server.extractors.llm_extractor import LlmExtractor

    return [
        RegexExtractor(),
        KeywordExtractor(),
        SpatialExtractor(),
        TableExtractor(),
        TableKVExtractor(),
        SectionExtractor(),
        NerExtractor(),
        LlmExtractor(),
    ]


def process_document(filepath: str) -> dict:
    """Run the full pipeline. Returns a JSON-serializable dict."""

    # Layer 1: Parse
    doc: Document = parse_any(filepath)

    # File metadata (best-effort)
    try:
        file_meta = extract_file_metadata(filepath)
    except Exception as e:
        log.debug("file metadata extraction failed: %s", e)
        file_meta = {"filename": os.path.basename(filepath)}

    # Layer 2: Schema discovery
    schema = discover_schema(doc)

    # Layer 3: Run all extractors
    extractors = _build_extractors()
    candidates_by_extractor = {}
    priors = {}
    for ex in extractors:
        priors[ex.name] = ex.prior
        try:
            candidates_by_extractor[ex.name] = ex.extract(doc, schema)
        except Exception as e:
            log.warning("extractor %s failed: %s", ex.name, e)
            candidates_by_extractor[ex.name] = []

    # Layer 4: Voting merge
    flag_threshold = float(os.getenv("CONFIDENCE_FLAG_THRESHOLD", "0.6"))
    fields, flagged = vote(schema, candidates_by_extractor, priors, flag_threshold=flag_threshold)

    # Layer 5: Build response
    return build_output(doc, schema, fields, flagged, file_meta)
