"""Confidence-weighted voting merger.

For each schema field, collect candidates from all extractors and pick the winner by:
   score = extractor_prior * confidence * validator_multiplier

If two candidates produce the same normalized value, their scores combine (consensus boost).
If the top two candidates disagree, the field is flagged.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from server.core.document import Candidate, FieldCandidate
from server.validators import validate

log = logging.getLogger(__name__)


def _normalize_value(v: Any) -> str:
    s = str(v).strip().lower()
    return re.sub(r"\s+", " ", s)


class FieldResult(dict):
    """Plain dict so it serializes cleanly."""


def vote(
    schema: list[FieldCandidate],
    candidates_by_extractor: dict[str, list[Candidate]],
    extractor_priors: dict[str, float],
    flag_threshold: float = 0.6,
) -> tuple[dict[str, FieldResult], list[str]]:
    """Returns (fields, flagged_field_names)."""

    fields: dict[str, FieldResult] = {}
    flagged: list[str] = []

    # Index candidates by field
    by_field: dict[str, list[Candidate]] = defaultdict(list)
    for ex_name, cands in candidates_by_extractor.items():
        for c in cands:
            by_field[c.field].append(c)

    schema_index = {fc.name: fc for fc in schema}

    for field_name in set(list(by_field.keys()) + list(schema_index.keys())):
        cands = by_field.get(field_name, [])
        if not cands:
            continue
        fc = schema_index.get(field_name)
        data_type = fc.data_type if fc else "string"

        # Validate each candidate; compute score
        scored: list[tuple[float, Candidate, bool, Any]] = []
        for c in cands:
            ok, normalized = validate(data_type, c.value)
            mult = 1.0 if ok else 0.6
            prior = extractor_priors.get(c.source, 0.5)
            score = prior * c.confidence * mult
            scored.append((score, c, ok, normalized))

        # Group by normalized value to combine consensus
        groups: dict[str, list[tuple[float, Candidate, bool, Any]]] = defaultdict(list)
        for tup in scored:
            groups[_normalize_value(tup[1].value)].append(tup)

        ranked: list[tuple[float, list[tuple[float, Candidate, bool, Any]]]] = []
        for key, items in groups.items():
            combined = sum(x[0] for x in items) * (1.0 + 0.15 * (len(items) - 1))
            ranked.append((combined, items))
        ranked.sort(key=lambda x: -x[0])

        winner_score, winner_items = ranked[0]
        winner_score_top, winner_cand, winner_ok, winner_norm = max(winner_items, key=lambda x: x[0])

        # Disagreement detection: a competing group with score within 25% of the winner
        disagreement = (
            len(ranked) > 1 and ranked[1][0] >= 0.75 * winner_score
        )

        evidences = []
        sources = []
        source_quotes = []
        for _, c, _, _ in winner_items:
            sources.append(c.source)
            if c.evidence and c.evidence.source_quote:
                source_quotes.append(c.evidence.source_quote)
            ev = c.evidence.model_dump() if c.evidence else {}
            evidences.append({"source": c.source, **ev})

        # Confidence: winner_score normalized against the *winning extractor's*
        # prior, not the global mean.  This avoids penalizing a strong
        # single-source win just because other (potentially-irrelevant)
        # extractors have higher priors.
        winning_prior = max(extractor_priors.get(c.source, 0.5) for _, c, _, _ in winner_items)
        confidence = min(1.0, winner_score / max(1e-9, winning_prior))

        fields[field_name] = FieldResult(
            value=winner_norm if winner_ok else winner_cand.value,
            confidence=round(confidence, 3),
            sources=sorted(set(sources)),
            agreement_count=len(winner_items),
            validated=winner_ok,
            data_type=data_type,
            evidence=evidences,
            source_quote=source_quotes[0] if source_quotes else None,
        )

        if disagreement:
            flagged.append(field_name)
            fields[field_name]["flags"] = ["disagreement"]
        elif confidence < flag_threshold:
            flagged.append(field_name)
            fields[field_name]["flags"] = ["low_confidence"]
        else:
            fields[field_name]["flags"] = []

    return fields, flagged
