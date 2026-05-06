"""Input module: File upload handling and metadata extraction."""

import os
from datetime import datetime, timezone
from typing import Optional

import pypdf
import filetype


def extract_file_metadata(filepath: str) -> dict:
    """Extract file metadata using pypdf and filetype.

    Args:
        filepath: Path to the uploaded file

    Returns:
        dict with filename, file_size_bytes, mime_type, page_count, is_encrypted,
        creation_date, author, title, producer
    """
    stat = os.stat(filepath)
    file_size_bytes = stat.st_size
    filename = os.path.basename(filepath)

    # Detect MIME type using magic bytes
    kind = filetype.guess(filepath)
    mime_type = kind.mime if kind else "application/octet-stream"

    # Extract PDF metadata
    reader = pypdf.PdfReader(filepath)
    page_count = len(reader.pages)
    is_encrypted = reader.is_encrypted
    pdf_meta = reader.metadata or {}

    creation_date = _parse_pdf_date(pdf_meta.get("/CreationDate"))
    author = pdf_meta.get("/Author")
    title = pdf_meta.get("/Title")
    producer = pdf_meta.get("/Producer")

    return {
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "mime_type": mime_type,
        "page_count": page_count,
        "is_encrypted": is_encrypted,
        "creation_date": creation_date,
        "author": author,
        "title": title,
        "producer": producer,
    }


def _parse_pdf_date(raw: Optional[str]) -> Optional[str]:
    """Parse PDF date string (D:YYYYMMDDHHmmSS format) to ISO 8601.

    PDF date format: D:20240110091630Z+00'00'
    Returns ISO 8601: 2024-01-10T09:16:30+00:00
    """
    if not raw or not isinstance(raw, str) or not raw.startswith("D:"):
        return None

    try:
        # Extract YYYYMMDDHHMMSS part (14 characters after "D:")
        dt_str = raw[2:16]
        dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")

        # Check for timezone
        tz_part = raw[16:] if len(raw) > 16 else ""
        if tz_part.startswith("Z"):
            dt = dt.replace(tzinfo=timezone.utc)
        elif tz_part.startswith("+") or tz_part.startswith("-"):
            # Parse offset like +00'00' or -05'00'
            try:
                offset_str = tz_part.replace("'", "")
                if offset_str[0] in ("+", "-"):
                    sign = 1 if offset_str[0] == "+" else -1
                    hours = int(offset_str[1:3])
                    minutes = int(offset_str[3:5]) if len(offset_str) > 3 else 0
                    from datetime import timedelta
                    offset = timedelta(hours=sign * hours, minutes=sign * minutes)
                    dt = dt.replace(tzinfo=timezone(offset))
            except (ValueError, IndexError):
                pass

        return dt.isoformat()
    except (ValueError, IndexError):
        return None
