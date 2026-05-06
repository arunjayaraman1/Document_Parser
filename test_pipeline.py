#!/usr/bin/env python
"""End-to-end pipeline test without starting the server."""

import sys
import os
import json
from pathlib import Path

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from parser.parser import parse_document
from parser.input_module import extract_file_metadata
from extractor.rule_extractor import RuleExtractor
from extractor.merger import MergeAndBuild


def test_layer_1():
    """Test PDF parsing and metadata extraction."""
    print("\n" + "="*60)
    print("LAYER 1: PDF Parsing & Metadata Extraction")
    print("="*60)

    pdf_path = "server/parser/input-files/sample_sow.pdf"

    # Parse PDF
    print("\n✓ Parsing PDF...")
    result = parse_document(pdf_path)
    print(f"  - Extraction method: {result['extraction_method']}")
    print(f"  - Elements extracted: {len(result['elements'])}")

    # Extract metadata
    print("\n✓ Extracting metadata...")
    metadata = extract_file_metadata(pdf_path)
    print(f"  - Filename: {metadata['filename']}")
    print(f"  - Page count: {metadata['page_count']}")
    print(f"  - MIME type: {metadata['mime_type']}")
    print(f"  - File size: {metadata['file_size_bytes']} bytes")

    return result, metadata


def test_layer_2(parse_result):
    """Test rule-based extraction."""
    print("\n" + "="*60)
    print("LAYER 2: Rule-Based Extraction")
    print("="*60)

    markdown_text = parse_result["md_output"]
    elements = parse_result["elements"]

    print(f"\n✓ Running rule extractor...")
    extractor = RuleExtractor()
    rule_results = extractor.extract(text=markdown_text, elements=elements)

    print(f"  - Fields extracted: {len(rule_results['fields'])}")
    for field_name, field_data in rule_results["fields"].items():
        print(f"    • {field_name}: {field_data['value'][:50]}... (confidence: {field_data['confidence']})")

    return rule_results


def test_layer_3():
    """Test LLM schema detection (optional)."""
    print("\n" + "="*60)
    print("LAYER 3: LLM Schema Detection (Optional - requires API key)")
    print("="*60)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "sk-or-v1-your-key-here":
        print("\n⚠ OpenRouter API key not configured.")
        print("  LLM extraction will be skipped.")
        print("  To enable, set OPENROUTER_API_KEY in .env")
        return {"document_type": "unknown", "fields": []}

    print("\n✓ LLM schema detection available")
    print("  (Actual LLM calls happen when pipeline.py runs)")
    return None


def test_layer_4(parse_result, metadata, rule_results):
    """Test merge and output building."""
    print("\n" + "="*60)
    print("LAYER 4: Merge & Hierarchical Output")
    print("="*60)

    print("\n✓ Building final output...")

    # Create mock LLM results
    llm_results = {"document_type": "statement_of_work", "fields": []}

    # Merge
    merger = MergeAndBuild()
    elements_data = []
    for el in parse_result["elements"]:
        metadata_obj = getattr(el, "metadata", None)
        page_number = 1
        parent_id = None
        coordinates = {}

        if metadata_obj:
            page_number = getattr(metadata_obj, "page_number", 1)
            parent_id = getattr(metadata_obj, "parent_id", None)
            coords_obj = getattr(metadata_obj, "coordinates", None)
            if coords_obj:
                if hasattr(coords_obj, "get"):
                    coordinates = dict(coords_obj)
                else:
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

    final_output = merger.merge(
        rule_results=rule_results,
        llm_results=llm_results,
        document_metadata=metadata,
        extraction_method=parse_result["extraction_method"],
        elements_data=elements_data,
    )

    print(f"  - Document type: {final_output.document.type}")
    print(f"  - Fields extracted: {len(final_output.fields)}")
    print(f"  - Flagged fields: {len(final_output.flagged_fields)}")
    print(f"  - Elements in hierarchy: {len(final_output.elements)}")

    # Save sample output
    output_path = "test_output.json"
    with open(output_path, "w") as f:
        json.dump(final_output.model_dump(exclude_none=False), f, indent=2, default=str)
    print(f"\n✓ Sample output saved to {output_path}")

    return final_output


def main():
    """Run all tests."""
    print("\n" + "█" * 60)
    print("█  DOCUMENT INTELLIGENCE PIPELINE - FULL INTEGRATION TEST")
    print("█" * 60)

    try:
        # Layer 1
        parse_result, metadata = test_layer_1()

        # Layer 2
        rule_results = test_layer_2(parse_result)

        # Layer 3
        test_layer_3()

        # Layer 4
        final_output = test_layer_4(parse_result, metadata, rule_results)

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nThe pipeline is ready to run!")
        print("\nTo start the server:")
        print("  cd server")
        print("  python -m uvicorn main:app --reload")
        print("\nThen test with:")
        print("  curl -X POST http://127.0.0.1:8000/api/parse \\")
        print("    -F 'file=@server/parser/input-files/sample_sow.pdf'")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
