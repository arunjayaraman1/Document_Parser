"""Consensus over schema detectors — runs all and merges proposals."""

from __future__ import annotations

import re
from collections import defaultdict

from server.core.document import Document, FieldCandidate
from .heuristic_detector import HeuristicDetector
from .ner_detector import NerDetector
from .llm_detector import LlmDetector
from .outline_detector import OutlineDetector


# Common label synonyms → canonical snake_case name
_SYNONYMS = {
    "invoice_no": "invoice_number",
    "inv_no": "invoice_number",
    "invoice": "invoice_number",
    "po_no": "purchase_order_number",
    "po_number": "purchase_order_number",
    "ref_no": "reference_number",
    "ref": "reference_number",
    "amount_due": "total",
    "grand_total": "total",
    "total_amount": "total",
    "bill_to": "client_name",
    "ship_to": "client_name",
    "buyer": "client_name",
    "customer": "client_name",
    "vendor": "vendor_name",
    "supplier": "vendor_name",
    "from": "vendor_name",
    "issue_date": "invoice_date",
    "issued": "invoice_date",
    "date": "invoice_date",
    "pay_by": "due_date",
    "payment_due": "due_date",
    "expires": "expiration_date",
    "end_date": "expiration_date",
    "start_date": "effective_date",
    "from_date": "effective_date",
    "money": "amount",
}


def _normalize(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return _SYNONYMS.get(n, n)


def detect_schema(doc: Document) -> list[FieldCandidate]:
    """Run all detectors and merge proposals into a consensus list."""
    detectors = [HeuristicDetector(), OutlineDetector(), NerDetector(), LlmDetector()]
    bucket: dict[str, list[FieldCandidate]] = defaultdict(list)

    for d in detectors:
        try:
            for fc in d.propose(doc):
                bucket[_normalize(fc.name)].append(fc)
        except Exception:
            continue

    final: list[FieldCandidate] = []
    for canon, group in bucket.items():
        # Keep if 2+ detectors agree, OR a single high-confidence proposal
        n_detectors = len({fc.detected_by for fc in group})
        max_conf = max(fc.confidence for fc in group)
        if n_detectors >= 2 or max_conf >= 0.6:
            best = max(group, key=lambda fc: fc.confidence)
            # prefer specific data types over "string"
            data_types = [fc.data_type for fc in group if fc.data_type != "string"]
            data_type = data_types[0] if data_types else best.data_type
            final.append(
                FieldCandidate(
                    name=canon,
                    data_type=data_type,
                    description=best.description,
                    confidence=min(1.0, max_conf + 0.1 * (n_detectors - 1)),
                    detected_by=",".join(sorted({fc.detected_by for fc in group})),
                )
            )
    final.sort(key=lambda fc: -fc.confidence)
    return final
