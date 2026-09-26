"""
Utility functions for text normalization, hashing, URL canonicalization, and slug generation.
"""
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Optional
import unicodedata
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

# Query parameters commonly used for tracking that do not alter content
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
    "trk",
    "_hsenc",
    "_hsmi",
    "mc_cid",
    "mc_eid",
}


def slugify(text: str) -> str:
    """Generate a clean URL slug from arbitrary text."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


def normalize_content_for_hash(content: str) -> str:
    """
    Normalize text content before hashing so benign formatting variations
    (e.g., CRLF line breaks, trailing spaces, extra empty lines) do not alter the hash.
    """
    if not content:
        return ""
    # Standardize line breaks
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing whitespace on each line
    lines = [line.strip() for line in text.split("\n")]
    # Collapse multiple consecutive blank lines
    normalized_lines = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                normalized_lines.append("")
                prev_blank = True
        else:
            normalized_lines.append(line)
            prev_blank = False
    return "\n".join(normalized_lines).strip()


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of normalized content for stable change detection."""
    normalized = normalize_content_for_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    """Normalize a title for matching and deduplication."""
    if not title:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    return " ".join(cleaned.split())


def canonicalize_url(url: str) -> str:
    """
    Canonicalize a URL by stripping tracking parameters, fragments,
    and trailing slashes while preserving canonical query parameters in sorted order.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        # Filter out tracking query parameters
        filtered_query = []
        for key, val in parse_qsl(parsed.query, keep_blank_values=False):
            if key.lower() not in TRACKING_PARAMS:
                filtered_query.append((key, val))
        filtered_query.sort()
        query = urlencode(filtered_query)

        # Drop fragment
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url.strip()


def parse_iso_datetime(val: Any) -> Optional[datetime]:
    """
    Robust ISO-8601 and flexible datetime parser.
    Handles:
    - Native datetime objects (ensures timezone-aware in UTC if naive)
    - ISO-8601 strings with 'Z' or timezone offsets
    - Timestamps (float or int milliseconds or seconds)
    - Standard date formats (YYYY-MM-DD, etc.)
    Returns timezone-aware datetime in UTC or normalized offset, or None if unparseable.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val

    # Epoch timestamp as int or float
    if isinstance(val, (int, float)):
        try:
            ts = float(val)
            if ts > 1e11:  # Milliseconds epoch
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    val_str = str(val).strip()
    if not val_str:
        return None

    # Check numeric string timestamp
    if re.match(r"^\d{10}(\.\d+)?$", val_str):
        try:
            return datetime.fromtimestamp(float(val_str), tz=timezone.utc)
        except Exception:
            pass
    elif re.match(r"^\d{13}$", val_str):
        try:
            return datetime.fromtimestamp(float(val_str) / 1000.0, tz=timezone.utc)
        except Exception:
            pass

    # Normalize 'Z' or 'z' to '+00:00'
    normalized = val_str
    if normalized.endswith("Z") or normalized.endswith("z"):
        normalized = normalized[:-1] + "+00:00"

    # Try standard Python fromisoformat
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Fallback to standard string formats
    formats = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue

    return None
