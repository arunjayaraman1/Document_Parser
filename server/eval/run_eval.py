"""Eval harness: run the pipeline against fixtures, compare to golden JSON, emit metrics.

Usage:
    python -m server.eval.run_eval
    python -m server.eval.run_eval --fixture invoice.pdf

Golden JSON format:
    {
        "expected_doc_type": "invoice",
        "fields": {
            "invoice_number": "INV-001",
            "total": "$1,234.56",
            "invoice_date": "2024-01-10"
        }
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from server.pipeline import process_document

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
GOLDEN = ROOT / "golden"


def _norm(v):
    if v is None:
        return ""
    s = str(v).strip().lower()
    return re.sub(r"[\s,$]+", "", s)


def evaluate(fixture: Path, golden: dict) -> dict:
    t0 = time.perf_counter()
    result = process_document(str(fixture))
    elapsed = time.perf_counter() - t0

    expected = golden.get("fields", {})
    fields = result.get("fields", {})
    schema = {f["name"] for f in result.get("schema", [])}

    schema_recall = (
        len(set(expected.keys()) & schema) / max(1, len(expected))
        if expected
        else None
    )

    tp = fp = fn = 0
    per_field = {}
    for name, expected_value in expected.items():
        got = fields.get(name, {}).get("value") if name in fields else None
        ok = _norm(got) == _norm(expected_value)
        per_field[name] = {
            "expected": expected_value,
            "got": got,
            "match": ok,
            "sources": fields.get(name, {}).get("sources", []),
        }
        if ok:
            tp += 1
        elif got is None:
            fn += 1
        else:
            fp += 1
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    return {
        "fixture": fixture.name,
        "elapsed_seconds": round(elapsed, 2),
        "doc_type": result.get("document", {}).get("type"),
        "expected_doc_type": golden.get("expected_doc_type"),
        "parse_method": result.get("document", {}).get("parse_method"),
        "schema_size": len(schema),
        "schema_recall": round(schema_recall, 3) if schema_recall is not None else None,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "fields": per_field,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=None, help="single fixture filename")
    ap.add_argument("--out", default=None, help="optional output JSON path")
    args = ap.parse_args()

    if not FIXTURES.exists():
        print(f"No fixtures dir at {FIXTURES}", file=sys.stderr)
        sys.exit(2)

    targets = []
    if args.fixture:
        p = FIXTURES / args.fixture
        if not p.exists():
            print(f"fixture not found: {p}", file=sys.stderr)
            sys.exit(2)
        targets = [p]
    else:
        targets = sorted([p for p in FIXTURES.iterdir() if p.is_file() and not p.name.startswith(".")])

    summary = []
    for fx in targets:
        gold_path = GOLDEN / f"{fx.stem}.json"
        if not gold_path.exists():
            print(f"⚠ no golden for {fx.name}; skipping (create {gold_path.name})")
            continue
        gold = json.loads(gold_path.read_text())
        try:
            res = evaluate(fx, gold)
        except Exception as e:
            res = {"fixture": fx.name, "error": str(e)}
        summary.append(res)
        print(json.dumps(res, indent=2, default=str))

    total = {
        "fixtures": len(summary),
        "avg_f1": round(
            sum(r.get("f1", 0) for r in summary) / max(1, len(summary)), 3
        ),
        "results": summary,
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(
        {"fixtures": total["fixtures"], "avg_f1": total["avg_f1"]},
        indent=2,
    ))

    if args.out:
        Path(args.out).write_text(json.dumps(total, indent=2, default=str))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
