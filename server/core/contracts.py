"""Protocols for the four pluggable layers of the pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .document import Candidate, Document, FieldCandidate


@runtime_checkable
class FileAdapter(Protocol):
    name: str
    accepts: set[str]  # MIME types

    def parse(self, path: str) -> Document: ...


@runtime_checkable
class SchemaDetector(Protocol):
    name: str

    def propose(self, doc: Document) -> list[FieldCandidate]: ...


@runtime_checkable
class FieldExtractor(Protocol):
    name: str
    prior: float  # confidence prior used by the voting merger

    def extract(self, doc: Document, schema: list[FieldCandidate]) -> list[Candidate]: ...


@runtime_checkable
class Validator(Protocol):
    data_type: str

    def validate(self, value) -> tuple[bool, object]:
        """Return (ok, normalized_value)."""
        ...
