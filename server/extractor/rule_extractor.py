"""Rule-based field extraction using regex, keyword proximity, and spatial matching."""

import re
from typing import Optional, Any
from datetime import datetime


class RuleExtractor:
    """Extract high-confidence fields using deterministic rules."""

    # Regex patterns for common document fields
    PATTERNS = {
        "date": re.compile(
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}"
            r"|(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})"
            r"|(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})",
            re.IGNORECASE
        ),
        "currency_amount": re.compile(
            r"(?:\$|USD|€|£|¥)\s*[\d,]+(?:\.\d{2})?"
            r"|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)"
        ),
        "invoice_number": re.compile(
            r"(?:Invoice|INV|Inv\.?)\s*[#\-:No\.]*\s*([A-Z0-9\-]{4,20})"
            r"|(?:Invoice\s+Number|Invoice\s+No\.?)\s*[:.]?\s*([A-Z0-9\-]{4,20})",
            re.IGNORECASE
        ),
        "reference_number": re.compile(
            r"(?:SOW|PO|Contract|Ref\.?|Reference)\s*[#\-:No\.]*\s*([A-Z0-9\-]{4,30})",
            re.IGNORECASE
        ),
        "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "phone": re.compile(
            r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        ),
        "percentage": re.compile(r"(\d+(?:\.\d+)?)\s*%"),
        "dollar_amount": re.compile(r"\$[\d,]+(?:\.\d{2})?"),
    }

    # Keywords that indicate field labels
    FIELD_KEYWORDS = {
        "invoice_number": ["Invoice", "INV", "Inv", "Invoice #", "Invoice No"],
        "invoice_date": ["Invoice Date", "Date", "Issue Date", "Issued"],
        "due_date": ["Due Date", "Payment Due", "Pay By", "Due"],
        "total": ["Total", "Total Amount", "Grand Total", "Amount Due"],
        "vendor_name": ["Vendor", "Supplier", "Bill From", "Service Provider", "From"],
        "client_name": ["Client", "Bill To", "Buyer", "Customer", "To"],
        "amount": ["Amount", "Total", "Value", "Cost"],
        "sow_reference": ["SOW", "SOW Reference", "SOW #", "SOW No"],
        "project_name": ["Project", "Project Name", "Title"],
        "effective_date": ["Effective Date", "Start Date", "From Date"],
        "expiration_date": ["Expiration Date", "End Date", "To Date", "Expires"],
        "payment_terms": ["Payment Terms", "Terms", "Payment", "Net"],
    }

    def __init__(self):
        self.extracted_fields = {}
        self.unmatched_field_names = []

    def extract_by_regex(self, text: str, elements: list = None) -> dict:
        """Extract fields using regex patterns.

        Args:
            text: Document text
            elements: List of elements (for bbox lookup)

        Returns:
            dict mapping field_name -> {value, confidence, method, element_id, page, bbox}
        """
        results = {}

        for field_name, pattern in self.PATTERNS.items():
            match = pattern.search(text)
            if match:
                matched_value = match.group(0)

                # Try to find which element this matched value came from
                element_id = None
                page = None
                bbox = None

                if elements:
                    for el in elements:
                        if hasattr(el, "text") and matched_value in el.text:
                            element_id = getattr(el, "element_id", None)
                            metadata = getattr(el, "metadata", None)
                            if metadata:
                                page = getattr(metadata, "page_number", None)
                                coords = getattr(metadata, "coordinates", None)
                                if coords:
                                    points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                                    if points:
                                        xs = [p[0] for p in points]
                                        ys = [p[1] for p in points]
                                        bbox = {
                                            "x1": min(xs),
                                            "y1": min(ys),
                                            "x2": max(xs),
                                            "y2": max(ys),
                                        }
                            break

                results[field_name] = {
                    "value": matched_value,
                    "confidence": 1.0,
                    "method": "regex",
                    "element_id": element_id,
                    "page": page,
                    "bbox": bbox,
                }

        return results

    def extract_by_keyword_proximity(
        self, text: str, elements: list = None, window: int = 100
    ) -> dict:
        """Extract fields by finding keyword labels and nearby values.

        For each known field keyword (e.g., "Invoice Number"),
        find the label in text and extract the next N characters as the value.

        Args:
            text: Document text
            elements: List of elements (for bbox lookup)
            window: Maximum characters to search after keyword

        Returns:
            dict mapping field_name -> {value, confidence, method, element_id, page, bbox}
        """
        results = {}

        for field_name, keywords in self.FIELD_KEYWORDS.items():
            for keyword in keywords:
                # Pattern: keyword + optional punctuation + value
                pattern = re.escape(keyword) + r"\s*[:\-]?\s*(.{1," + str(window) + r"}?)(?:\n|$)"
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Clean up the value (remove trailing punctuation, extra whitespace)
                    value = re.sub(r"[.,;:]*\s*$", "", value).strip()
                    if value and len(value) > 2:  # Filter out noise

                        # Try to find which element this value came from
                        element_id = None
                        page = None
                        bbox = None

                        if elements:
                            for el in elements:
                                if hasattr(el, "text") and (keyword.lower() in el.text.lower() or value in el.text):
                                    element_id = getattr(el, "element_id", None)
                                    metadata = getattr(el, "metadata", None)
                                    if metadata:
                                        page = getattr(metadata, "page_number", None)
                                        coords = getattr(metadata, "coordinates", None)
                                        if coords:
                                            points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                                            if points:
                                                xs = [p[0] for p in points]
                                                ys = [p[1] for p in points]
                                                bbox = {
                                                    "x1": min(xs),
                                                    "y1": min(ys),
                                                    "x2": max(xs),
                                                    "y2": max(ys),
                                                }
                                    break

                        results[field_name] = {
                            "value": value,
                            "confidence": 0.85,
                            "method": "keyword_proximity",
                            "element_id": element_id,
                            "page": page,
                            "bbox": bbox,
                        }
                        break  # Use first matching keyword for this field

        return results

    def extract_by_spatial_proximity(self, elements: list) -> dict:
        """Extract fields using bounding box spatial relationships.

        For form-style documents: find a label element and extract
        the element nearest to its right on the same horizontal line.

        Args:
            elements: List of unstructured elements with metadata.coordinates

        Returns:
            dict mapping field_name -> (matched_value, confidence)
        """
        results = {}
        max_horizontal_gap = 200  # pixels
        same_line_tolerance = 5   # pixels

        # Build a searchable index of elements
        label_keywords = {
            "invoice_number": "Invoice",
            "invoice_date": "Date",
            "due_date": "Due",
            "total": "Total",
            "vendor_name": "Vendor",
            "client_name": "Client",
            "sow_reference": "SOW",
            "project_name": "Project",
        }

        for field_name, label_text in label_keywords.items():
            # Find label element
            label_el = None
            for el in elements:
                if hasattr(el, "text") and label_text.lower() in el.text.lower():
                    label_el = el
                    break

            if not label_el or not hasattr(label_el, "metadata"):
                continue

            # Get label's right edge coordinates
            try:
                metadata = label_el.metadata
                # ElementMetadata is an object, access coordinates attribute
                coords = getattr(metadata, "coordinates", None)
                if coords is None:
                    continue
                # coordinates is a dict-like object, get points
                points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                if not points or len(points) < 3:
                    continue
                # points format: [[x1,y1], [x1,y2], [x2,y2], [x2,y1]]
                label_x_right = points[2][0]  # right edge
                label_y = points[0][1]         # vertical center
            except (KeyError, IndexError, TypeError, AttributeError):
                continue

            # Find value element to the right on same line
            candidates = []
            for el in elements:
                if not hasattr(el, "metadata") or el == label_el:
                    continue

                try:
                    metadata = el.metadata
                    coords = getattr(metadata, "coordinates", None)
                    if coords is None:
                        continue
                    points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                    if not points or len(points) < 3:
                        continue
                    val_x_left = points[0][0]   # left edge
                    val_y = points[0][1]         # vertical center

                    # Check if on same line and to the right
                    if (abs(val_y - label_y) < same_line_tolerance and
                        0 < (val_x_left - label_x_right) < max_horizontal_gap):
                        candidates.append(el)
                except (KeyError, IndexError, TypeError, AttributeError):
                    continue

            if candidates:
                # Use the nearest candidate (leftmost)
                def get_x_coord(e):
                    try:
                        coords = getattr(e.metadata, "coordinates", None)
                        points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                        return points[0][0] if points else float('inf')
                    except:
                        return float('inf')

                nearest = min(candidates, key=get_x_coord)
                if hasattr(nearest, "text"):
                    # Extract bbox from nearest element
                    element_id = getattr(nearest, "element_id", None)
                    page = None
                    bbox = None

                    metadata = getattr(nearest, "metadata", None)
                    if metadata:
                        page = getattr(metadata, "page_number", None)
                        coords = getattr(metadata, "coordinates", None)
                        if coords:
                            points = coords.get("points", []) if hasattr(coords, "get") else getattr(coords, "points", [])
                            if points:
                                xs = [p[0] for p in points]
                                ys = [p[1] for p in points]
                                bbox = {
                                    "x1": min(xs),
                                    "y1": min(ys),
                                    "x2": max(xs),
                                    "y2": max(ys),
                                }

                    results[field_name] = {
                        "value": nearest.text.strip(),
                        "confidence": 0.8,
                        "method": "spatial",
                        "element_id": element_id,
                        "page": page,
                        "bbox": bbox,
                    }

        return results

    def extract(
        self, text: str, elements: list = None
    ) -> dict:
        """Extract all high-confidence fields using all available methods.

        Args:
            text: Document text
            elements: Optional list of unstructured elements (for spatial matching)

        Returns:
            dict with:
            - "fields": extracted field_name -> {value, confidence, method, element_id, page, bbox}
            - "unmatched_keywords": list of field keywords that weren't matched
        """
        # Run all extraction methods
        regex_results = self.extract_by_regex(text, elements)
        keyword_results = self.extract_by_keyword_proximity(text, elements)
        spatial_results = self.extract_by_spatial_proximity(elements) if elements else {}

        # Merge results (priority: spatial > keyword > regex)
        all_results = {}
        all_results.update(regex_results)
        all_results.update(keyword_results)
        all_results.update(spatial_results)

        # Identify unmatched keywords
        all_keywords = set()
        for keywords in self.FIELD_KEYWORDS.values():
            all_keywords.update(k.lower() for k in keywords)

        matched_keywords = set(
            k.lower() for field_name in all_results.keys()
            for k in self.FIELD_KEYWORDS.get(field_name, [])
        )
        unmatched = list(all_keywords - matched_keywords)

        return {
            "fields": all_results,
            "unmatched_keywords": unmatched,
        }
