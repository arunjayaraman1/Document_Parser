"""Pydantic models for document extraction pipeline."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal


# ── Schema Detection Models ──────────────────────────────────────────────────

class DetectedField(BaseModel):
    """A field detected in the document schema."""

    name: str = Field(description="Snake_case field name")
    data_type: Literal["string", "number", "date", "boolean", "list"] = Field(
        description="Expected data type for this field"
    )
    description: Optional[str] = Field(
        None, description="Brief description of what this field represents"
    )


class DocumentSchema(BaseModel):
    """Schema detected for a document."""

    document_type: str = Field(
        description="Type of document (invoice, contract, sow, purchase_order, receipt, proposal, other)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in document type classification (0.0-1.0)"
    )
    fields: list[DetectedField] = Field(
        description="List of field definitions detected in this document"
    )


# ── Data Extraction Models ───────────────────────────────────────────────────

class ExtractedField(BaseModel):
    """An extracted field with value and metadata."""

    field_name: str = Field(description="Name of the field")
    value: Optional[Any] = Field(None, description="Extracted value")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence score for this extraction (0.0-1.0)"
    )
    source_quote: Optional[str] = Field(
        None, description="Verbatim text from document supporting this value"
    )


class ExtractionResult(BaseModel):
    """Result of field value extraction."""

    fields: list[ExtractedField] = Field(description="List of extracted fields")
    extraction_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Overall confidence in extraction quality"
    )


# ── Final Output Models ──────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """Bounding box coordinates in pixels (PixelSpace)."""

    x1: float = Field(description="Left edge")
    y1: float = Field(description="Top edge")
    x2: float = Field(description="Right edge")
    y2: float = Field(description="Bottom edge")


class DocumentMetadata(BaseModel):
    """File and document metadata."""

    filename: str
    file_size_bytes: int
    mime_type: str
    page_count: int
    is_encrypted: bool
    creation_date: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    producer: Optional[str] = None
    layout_width: float = Field(default=595.28, description="Page width in pixels")
    layout_height: float = Field(default=841.89, description="Page height in pixels")


class DocumentInfo(BaseModel):
    """Document classification and extraction metadata."""

    type: str = Field(description="Document type (invoice, contract, sow, etc.)")
    extraction_method: Literal["fast", "ocr_only"] = Field(
        description="Which PDF extraction method was used"
    )
    is_scanned: bool = Field(
        description="Whether document was extracted via OCR (scanned PDF)"
    )
    metadata: DocumentMetadata


class FinalExtractedField(BaseModel):
    """A field in the final output with full traceability."""

    value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["rule", "llm"] = Field(description="Extraction method")
    element_id: Optional[str] = Field(None, description="ID of source element")
    page: Optional[int] = Field(None, description="Page number")
    bbox: Optional[BoundingBox] = None
    source_quote: Optional[str] = Field(None, description="For LLM extractions only")


class Element(BaseModel):
    """A document element with hierarchy and position."""

    element_id: str
    type: str = Field(description="Element type (Header, Title, NarrativeText, Table, etc.)")
    text: str
    page: int
    bbox: BoundingBox
    parent_id: Optional[str] = None
    matched_field: Optional[str] = Field(
        None, description="Field name if this element was the source of an extraction"
    )
    children: list["Element"] = Field(default_factory=list)


Element.model_rebuild()  # For recursive model


class FinalOutput(BaseModel):
    """Complete output of document parsing and extraction."""

    document: DocumentInfo
    fields: dict[str, FinalExtractedField] = Field(
        description="Extracted fields keyed by field name"
    )
    flagged_fields: list[str] = Field(
        default_factory=list,
        description="Field names with confidence below threshold, flagged for review",
    )
    elements: list[Element] = Field(
        description="Full document structure with bounding boxes and hierarchy"
    )
