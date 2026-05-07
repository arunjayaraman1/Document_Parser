#!/usr/bin/env python
"""Smoke test for the new pipeline.

Tests the voting merger and heuristic schema detector with no heavy deps,
plus optional end-to-end run if a file path is provided.

    python test_pipeline.py
    python test_pipeline.py server/parser/input-files/sample_invoice.pdf
"""

from __future__ import annotations

import json
import sys


def smoke_test_voting():
    from server.core.document import FieldCandidate, Candidate, Evidence
    from server.merge.voting import vote

    schema = [FieldCandidate(name="invoice_number", data_type="id", detected_by="heuristic")]
    cand_by = {
        "regex": [Candidate(field="invoice_number", value="INV-001", confidence=0.95,
                            source="regex", evidence=Evidence(method_detail="regex:id"))],
        "ner":   [Candidate(field="invoice_number", value="INV-001", confidence=0.7,
                            source="ner",   evidence=Evidence(method_detail="ner"))],
        "llm":   [Candidate(field="invoice_number", value="INV-002", confidence=0.6,
                            source="llm",   evidence=Evidence())],
    }
    priors = {"regex": 0.95, "ner": 0.7, "llm": 0.85}
    fields, _ = vote(schema, cand_by, priors)
    assert fields["invoice_number"]["value"] == "INV-001"
    assert "regex" in fields["invoice_number"]["sources"]
    print("✓ voting merger picks consensus winner")


def smoke_test_heuristic():
    from server.core.document import Document
    from server.schema.heuristic_detector import HeuristicDetector

    doc = Document(raw_markdown=(
        "Invoice Number: INV-001\n"
        "Invoice Date: 2024-01-10\n"
        "Total: $1,234.56\n"
        "Email: foo@bar.com"
    ))
    types = {f.name: f.data_type for f in HeuristicDetector().propose(doc)}
    assert types.get("invoice_date") == "date"
    assert types.get("total") == "currency"
    assert types.get("email") == "email"
    print("✓ heuristic schema detector infers types")


def end_to_end(path: str):
    from server.pipeline import process_document
    out = process_document(path)
    print(json.dumps({
        "document": out["document"],
        "schema": [s["name"] for s in out["schema"]],
        "fields": list(out.get("fields", {}).keys()),
        "flagged_fields": out.get("flagged_fields", []),
    }, indent=2))


if __name__ == "__main__":
    smoke_test_voting()
    smoke_test_heuristic()
    if len(sys.argv) >= 2:
        end_to_end(sys.argv[1])
    print("\nALL SMOKES PASSED")
