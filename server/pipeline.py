"""Main document intelligence pipeline: Orchestrates all 4 layers."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser.parser import parse_document
from parser.input_module import extract_file_metadata
from extractor.rule_extractor import RuleExtractor
from extractor.merger import MergeAndBuild
from extractor.models import FinalOutput
from llm.schema_extractor import detect_schema
from llm.data_extractor import extract_fields


async def process_document(filepath: str) -> FinalOutput:
    """Process a document through all 4 layers of the pipeline.

    Args:
        filepath: Path to the uploaded PDF file

    Returns:
        FinalOutput with structured document data and bounding boxes
    """

    # ── Layer 1: PDF Parsing & Metadata ──────────────────────────────────────

    # Parse document with parallel fast + OCR
    parse_result = parse_document(filepath)
    elements = parse_result["elements"]
    markdown_text = parse_result["md_output"]
    extraction_method = parse_result["extraction_method"]

    # Extract file metadata
    file_metadata = extract_file_metadata(filepath)

    # ── Layer 2: Rule-Based Extraction ────────────────────────────────────────

    rule_extractor = RuleExtractor()
    rule_results = rule_extractor.extract(text=markdown_text, elements=elements)

    # ── Layer 3: LLM Extraction ──────────────────────────────────────────────

    # Skip LLM if no API key is configured (for development/testing)
    llm_results = None
    try:
        # Step 1: Detect schema (document type + field names)
        schema = detect_schema(markdown_text)

        # Step 2: Extract field values for detected fields
        if schema.fields:
            extraction = extract_fields(markdown_text, schema.fields)
            llm_results = {
                "document_type": schema.document_type,
                "fields": [
                    {
                        "field_name": f.field_name,
                        "value": f.value,
                        "confidence": f.confidence,
                        "source_quote": f.source_quote,
                    }
                    for f in extraction.fields
                ],
            }
        else:
            llm_results = {
                "document_type": schema.document_type,
                "fields": [],
            }
    except (ValueError, Exception) as e:
        # LLM not configured or error occurred
        # Fallback to rule-based only
        print(f"LLM extraction skipped: {e}")
        llm_results = {
            "document_type": "unknown",
            "fields": [],
        }

    # ── Layer 4: Merge & Build Output ────────────────────────────────────────

    merger = MergeAndBuild()

    # Convert elements to dict format for merger
    elements_data = []
    if elements:
        for el in elements:
            # Extract metadata - it's an object, not a dict
            metadata = getattr(el, "metadata", None)
            page_number = 1
            parent_id = None
            coordinates = {}

            if metadata:
                # metadata is an ElementMetadata object
                page_number = getattr(metadata, "page_number", 1)
                parent_id = getattr(metadata, "parent_id", None)
                coords_obj = getattr(metadata, "coordinates", None)
                if coords_obj:
                    # coordinates is a dict-like object
                    if hasattr(coords_obj, "get"):
                        coordinates = dict(coords_obj)
                    else:
                        # Try to extract as dict
                        coordinates = {
                            "points": getattr(coords_obj, "points", []),
                            "layout_height": getattr(coords_obj, "layout_height", 841.89),
                            "layout_width": getattr(coords_obj, "layout_width", 595.28),
                            "system": getattr(coords_obj, "system", "PixelSpace"),
                        }

            el_dict = {
                "element_id": getattr(el, "element_id", ""),
                "type": getattr(el, "__class__", type(el)).__name__,
                "text": getattr(el, "text", ""),
                "metadata": {
                    "page_number": page_number,
                    "parent_id": parent_id,
                    "coordinates": coordinates,
                },
            }
            elements_data.append(el_dict)

    # Merge results and build final hierarchical output
    final_output = merger.merge(
        rule_results=rule_results,
        llm_results=llm_results,
        document_metadata={
            "filename": file_metadata.get("filename"),
            "file_size_bytes": file_metadata.get("file_size_bytes"),
            "mime_type": file_metadata.get("mime_type"),
            "page_count": file_metadata.get("page_count"),
            "is_encrypted": file_metadata.get("is_encrypted"),
            "creation_date": file_metadata.get("creation_date"),
            "author": file_metadata.get("author"),
            "title": file_metadata.get("title"),
            "producer": file_metadata.get("producer"),
        },
        extraction_method=extraction_method,
        elements_data=elements_data,
    )

    return final_output
