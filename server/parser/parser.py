from concurrent.futures import ThreadPoolExecutor
import os

try:
    from unstructured.partition.pdf import partition_pdf
except ImportError as exc:
    raise ImportError(
        "Could not import 'partition_pdf' from 'unstructured.partition.pdf'. "
        "Install the 'unstructured' package and verify the import path."
    ) from exc

try:
    from unstructured.staging.base import elements_to_json, elements_to_md
except ImportError as exc:
    raise ImportError(
        "Could not import 'elements_to_json' or 'elements_to_md' from 'unstructured.staging.base'. "
        "Install the 'unstructured' package and verify the import path."
    ) from exc


def _run_fast(filepath: str):
    """Run fast (pdfminer) extraction."""
    return partition_pdf(filename=filepath, strategy="fast")


def _run_ocr(filepath: str):
    """Run OCR extraction."""
    return partition_pdf(filename=filepath, strategy="ocr_only")


def _text_length(elements) -> int:
    """Calculate total text length from elements."""
    return sum(len(e.text) for e in elements if hasattr(e, "text"))


def parse_document(filepath: str) -> dict:
    """Parse a document using parallel fast + OCR extraction.

    Returns the result from whichever method finds text.
    Fast (pdfminer) is preferred if it finds any text.
    Falls back to OCR only if fast extraction yields empty results.
    """
    parse_strategy = os.getenv("PDF_PARSE_STRATEGY", "auto").lower()

    if parse_strategy == "fast":
        elements = partition_pdf(filename=filepath, strategy="fast")
        method_used = "fast"
    elif parse_strategy == "ocr_only":
        elements = partition_pdf(filename=filepath, strategy="ocr_only")
        method_used = "ocr_only"
    else:  # auto (default)
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_fast = executor.submit(_run_fast, filepath)
            future_ocr = executor.submit(_run_ocr, filepath)
            fast_elements = future_fast.result()
            ocr_elements = future_ocr.result()

        # Binary win condition: any text found in fast → use fast; else → use OCR
        if _text_length(fast_elements) > 0:
            elements = fast_elements
            method_used = "fast"
        else:
            elements = ocr_elements
            method_used = "ocr_only"

    return {
        "elements": elements,
        "json_output": elements_to_json(elements, indent=2),
        "md_output": elements_to_md(elements),
        "extraction_method": method_used,
    }


def main():
    filepath = "/Users/newpage/Documents/Projects/Document-Parser/server/parser/input-files/sample_sow.pdf"
    result = parse_document(filepath)

    json_path = "/Users/newpage/Documents/Projects/Document-Parser/server/parser/output.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(result["json_output"])

    md_path = "/Users/newpage/Documents/Projects/Document-Parser/server/parser/output.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["md_output"])


if __name__ == "__main__":
    main()