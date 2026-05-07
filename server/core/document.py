"""Normalized document model — the stable contract between parsers and extractors.

Any parser adapter must produce a `Document`; any extractor must consume one.
Changing the parser layer should never require changing the extractors.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box in pixels (top-left origin)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)


class Page(BaseModel):
    page_no: int
    width: float = 595.28
    height: float = 841.89


ElementType = Literal[
    "title",
    "heading",
    "paragraph",
    "list_item",
    "table",
    "figure",
    "caption",
    "header",
    "footer",
    "footnote",
    "kv_label",
    "kv_value",
    "text",
]


class Element(BaseModel):
    """A single document element with text + position."""

    element_id: str
    type: ElementType = "text"
    text: str = ""
    page: int = 1
    bbox: Optional[BBox] = None
    parent_id: Optional[str] = None
    children: list["Element"] = Field(default_factory=list)


class TableCell(BaseModel):
    row: int
    col: int
    text: str
    bbox: Optional[BBox] = None
    is_header: bool = False
    rowspan: int = 1
    colspan: int = 1


class Table(BaseModel):
    table_id: str
    page: int
    bbox: Optional[BBox] = None
    rows: int
    cols: int
    cells: list[TableCell] = Field(default_factory=list)
    caption: Optional[str] = None

    def header_row(self) -> list[TableCell]:
        return [c for c in self.cells if c.is_header or c.row == 0]


class Document(BaseModel):
    """Parser-neutral document representation."""

    pages: list[Page] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    raw_markdown: str = ""
    raw_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    parse_method: list[str] = Field(
        default_factory=list,
        description="Ordered list of adapters that contributed (e.g. ['docling','pdfplumber']).",
    )

    def text_length(self) -> int:
        if self.raw_text:
            return len(self.raw_text)
        return sum(len(e.text) for e in self.elements)


# ── Extraction-side types ────────────────────────────────────────────────────


class Evidence(BaseModel):
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    element_id: Optional[str] = None
    source_quote: Optional[str] = None
    method_detail: Optional[str] = None


class FieldCandidate(BaseModel):
    """A schema field proposed by a SchemaDetector."""

    name: str
    data_type: Literal["string", "number", "date", "boolean", "list", "currency", "email", "phone", "id", "percentage"] = "string"
    description: Optional[str] = None
    confidence: float = 0.5
    detected_by: str  # "heuristic" | "ner" | "llm"


class Candidate(BaseModel):
    """A value extracted for a specific field by a specific extractor."""

    field: str
    value: Any
    confidence: float = 0.5
    source: str  # extractor name
    evidence: Evidence = Field(default_factory=Evidence)
    validated: Optional[bool] = None


Element.model_rebuild()
