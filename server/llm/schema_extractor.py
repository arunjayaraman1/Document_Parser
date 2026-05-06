"""LLM-based schema detection (Step 1): Identify document type and field names."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instructor
from extractor.models import DocumentSchema, DetectedField
from .client import get_instructor_client


def detect_schema(markdown_text: str) -> DocumentSchema:
    """Detect document schema using Qwen2.5-7B.

    Identifies document type and lists all fields present in the document.
    This is a cheap, fast operation (Qwen2.5-7B).

    Args:
        markdown_text: Clean markdown text of the document

    Returns:
        DocumentSchema with detected document type and field list
    """
    model = os.getenv("LLM_SCHEMA_MODEL", "qwen/qwen-2.5-7b-instruct")
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    client = get_instructor_client(mode=instructor.Mode.TOOLS)

    system_prompt = """You are a document classification expert. Analyze the provided document and:

1. Classify the document type (invoice, contract, statement of work, purchase order, receipt, proposal, or other)
2. Identify all meaningful data fields present in the document

Return the classification with a confidence score (0.0-1.0) and a list of field names in snake_case.
Only include fields that are explicitly present in the document - do not invent fields."""

    user_prompt = f"""Analyze this document and identify its type and fields:

{markdown_text[:3000]}"""

    result = client.chat.completions.create(
        model=model,
        response_model=DocumentSchema,
        max_retries=max_retries,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return result
