"""Layer 4: Merge rule + LLM results and build hierarchical output."""

import os
from typing import Optional
from datetime import datetime

from .models import (
    FinalOutput,
    FinalExtractedField,
    DocumentInfo,
    DocumentMetadata,
    BoundingBox,
    Element,
)


class MergeAndBuild:
    """Merge rule-based and LLM extraction results, build final hierarchical output."""

    def __init__(self):
        self.rule_fields = {}
        self.llm_fields = {}
        self.all_elements = {}
        self.element_hierarchy = {}

    def _normalize_bbox(self, points: list) -> Optional[BoundingBox]:
        """Convert unstructured points format to normalized BoundingBox.

        Points format: [[x1,y1], [x1,y2], [x2,y2], [x2,y1]]
        Returns: BoundingBox with x1, y1 (top-left), x2, y2 (bottom-right)
        """
        try:
            if not points or len(points) < 3:
                return None
            # Extract coordinates from points
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x1 = min(xs)
            x2 = max(xs)
            y1 = min(ys)
            y2 = max(ys)
            return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
        except (IndexError, TypeError, ValueError):
            pass
        return None

    def _build_element_tree(self, elements_data: list) -> tuple[list[Element], dict]:
        """Build hierarchical element tree from flat element list.

        Args:
            elements_data: List of element dicts from unstructured

        Returns:
            Tuple of (root_elements, all_elements_dict)
        """
        all_elements_dict = {}
        parent_map = {}

        # First pass: create all Element objects
        for el_data in elements_data:
            try:
                element_id = el_data.get("element_id", "")
                metadata = el_data.get("metadata", {})

                # Extract coordinates
                coords_data = metadata.get("coordinates", {})
                points = coords_data.get("points", []) if coords_data else []
                bbox = self._normalize_bbox(points)

                element = Element(
                    element_id=element_id,
                    type=el_data.get("type", "Text"),
                    text=el_data.get("text", ""),
                    page=metadata.get("page_number", 1),
                    bbox=bbox,
                    parent_id=metadata.get("parent_id"),
                )
                all_elements_dict[element_id] = element
                parent_id = element.parent_id
                if parent_id:
                    if parent_id not in parent_map:
                        parent_map[parent_id] = []
                    parent_map[parent_id].append(element_id)
            except Exception as e:
                # Skip malformed elements
                continue

        # Second pass: build hierarchy
        root_elements = []
        for element_id, element in all_elements_dict.items():
            if element.parent_id is None:
                root_elements.append(element)
            elif element.parent_id in all_elements_dict:
                parent = all_elements_dict[element.parent_id]
                parent.children.append(element)

        return root_elements, all_elements_dict

    def _confidence_score(
        self,
        source: str,
        value: Optional[str],
        source_quote: Optional[str] = None,
    ) -> float:
        """Calculate confidence score for an extracted field.

        Args:
            source: "rule" or "llm"
            value: The extracted value
            source_quote: Verbatim quote from document (for LLM extractions)

        Returns:
            Confidence score 0.0-1.0
        """
        if not value:
            return 0.0

        rule_score = float(os.getenv("CONFIDENCE_RULE_SCORE", "1.0"))
        llm_verified = float(os.getenv("CONFIDENCE_LLM_VERIFIED", "0.85"))
        llm_unverified = float(os.getenv("CONFIDENCE_LLM_UNVERIFIED", "0.5"))

        if source == "rule":
            return rule_score
        elif source == "llm":
            # If source_quote is provided and non-empty, assume higher confidence
            return llm_verified if source_quote else llm_unverified
        return 0.5

    def merge(
        self,
        rule_results: dict,
        llm_results: dict,
        document_metadata: dict,
        extraction_method: str,
        elements_data: list,
    ) -> FinalOutput:
        """Merge rule and LLM results into final hierarchical output.

        Args:
            rule_results: Output from rule_extractor.extract()
            llm_results: Output from LLM extraction pipeline
            document_metadata: File metadata
            extraction_method: "fast" or "ocr_only"
            elements_data: Raw elements from unstructured

        Returns:
            FinalOutput with merged fields and hierarchical structure
        """
        # Build element hierarchy
        root_elements, all_elements_dict = self._build_element_tree(elements_data)

        # Extract rule-based fields
        rule_fields = rule_results.get("fields", {})

        # Extract LLM fields
        llm_fields = {}
        if isinstance(llm_results, dict):
            llm_raw = llm_results.get("fields", [])
            if isinstance(llm_raw, list):
                for field in llm_raw:
                    if isinstance(field, dict):
                        llm_fields[field.get("field_name")] = field
            else:
                llm_fields = llm_raw

        # Merge: prefer rule fields, fill gaps with LLM
        merged_fields = {}
        confidence_threshold = float(os.getenv("CONFIDENCE_FLAG_THRESHOLD", "0.7"))
        flagged_fields = []

        # Add rule-based fields
        for field_name, field_data in rule_fields.items():
            confidence = field_data.get("confidence", 0.5)

            # Extract bbox if present
            bbox_data = field_data.get("bbox")
            bbox = None
            if bbox_data:
                bbox = BoundingBox(
                    x1=bbox_data.get("x1", 0),
                    y1=bbox_data.get("y1", 0),
                    x2=bbox_data.get("x2", 0),
                    y2=bbox_data.get("y2", 0),
                )

            merged_fields[field_name] = FinalExtractedField(
                value=field_data.get("value"),
                confidence=confidence,
                source="rule",
                element_id=field_data.get("element_id"),
                page=field_data.get("page"),
                bbox=bbox,
                source_quote=None,
            )
            if confidence < confidence_threshold:
                flagged_fields.append(field_name)

        # Add LLM fields (only if not already in rule results)
        for field_name, field_data in llm_fields.items():
            if field_name not in merged_fields and field_data.get("value"):
                confidence = self._confidence_score(
                    "llm",
                    field_data.get("value"),
                    field_data.get("source_quote"),
                )
                merged_fields[field_name] = FinalExtractedField(
                    value=field_data.get("value"),
                    confidence=confidence,
                    source="llm",
                    element_id=None,
                    page=None,
                    bbox=None,
                    source_quote=field_data.get("source_quote"),
                )
                if confidence < confidence_threshold:
                    flagged_fields.append(field_name)

        # Build document info
        document_type = llm_results.get("document_type", "unknown") if isinstance(llm_results, dict) else "unknown"
        document_info = DocumentInfo(
            type=document_type,
            extraction_method=extraction_method,
            is_scanned=(extraction_method == "ocr_only"),
            metadata=DocumentMetadata(
                filename=document_metadata.get("filename", "unknown"),
                file_size_bytes=document_metadata.get("file_size_bytes", 0),
                mime_type=document_metadata.get("mime_type", "application/octet-stream"),
                page_count=document_metadata.get("page_count", 0),
                is_encrypted=document_metadata.get("is_encrypted", False),
                creation_date=document_metadata.get("creation_date"),
                author=document_metadata.get("author"),
                title=document_metadata.get("title"),
                producer=document_metadata.get("producer"),
            ),
        )

        return FinalOutput(
            document=document_info,
            fields=merged_fields,
            flagged_fields=flagged_fields,
            elements=root_elements,
        )
