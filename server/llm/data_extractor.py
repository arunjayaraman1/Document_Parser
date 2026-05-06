"""LLM-based data extraction (Step 2): Extract field values with source quotes."""

import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instructor
from extractor.models import ExtractionResult, ExtractedField, DetectedField
from .client import get_instructor_client


def extract_fields(
    markdown_text: str,
    detected_fields: list[DetectedField],
) -> ExtractionResult:
    """Extract field values using Qwen3-30B.

    For each detected field, extract the value from the document.
    Includes source quotes for audit trail and confidence verification.

    Args:
        markdown_text: Clean markdown text of the document
        detected_fields: List of fields to extract (from schema detection step)

    Returns:
        ExtractionResult with extracted field values and confidence scores
    """
    model = os.getenv("LLM_EXTRACT_MODEL", "qwen/qwen3-30b-a3b")
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    client = get_instructor_client(mode=instructor.Mode.TOOLS)

    # Build field descriptions for the prompt
    field_descriptions = []
    for field in detected_fields:
        desc = f"- {field.name} ({field.data_type})"
        if field.description:
            desc += f": {field.description}"
        field_descriptions.append(desc)

    field_list_str = "\n".join(field_descriptions)

    system_prompt = """You are a precise document data extractor. Your task is to extract field values from documents.

For each field:
1. Extract the exact value as it appears in the document
2. Include a source quote (verbatim text from the document that supports this value)
3. If a field is not present, return null for the value
4. Assign a confidence score (0.0-1.0):
   - 1.0 = explicitly stated, easy to find
   - 0.7-0.9 = inferred from context, clearly present
   - 0.4-0.6 = ambiguous or partially present
   - 0.0 = not found

Format dates as ISO 8601 (YYYY-MM-DD) when extracting date values."""

    user_prompt = f"""Extract these fields from the document:

{field_list_str}

Document:
---
{markdown_text}
---

Return extracted values as JSON."""

    result = client.chat.completions.create(
        model=model,
        response_model=ExtractionResult,
        max_retries=max_retries,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return result
