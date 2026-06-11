from __future__ import annotations

import hashlib
import math
import re
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "igshid"}


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_value(value)).strip()


def normalize_phone(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_value(value))


def normalize_url(value: Any) -> str:
    text = clean_value(value)
    if not text:
        return ""
    if not re.match(r"^https?://", text, flags=re.I):
        text = f"https://{text}"
    parts = urlsplit(text)
    if not parts.netloc:
        return ""
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def to_float(value: Any) -> float:
    try:
        text = clean_value(value).replace(",", "")
        return float(text) if text else 0.0
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    return int(to_float(value))


def to_bool(value: Any) -> bool:
    return clean_value(value).lower() in {"true", "1", "yes", "y"}


def slugify(value: str, max_len: int = 80) -> str:
    text = clean_value(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "item"


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def ensure_parent(path: str | Path) -> Path:
    result = Path(path)
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def write_csv(rows: Iterable[dict[str, Any]], path: str | Path, columns: list[str] | None = None) -> None:
    output_path = ensure_parent(path)
    frame = pd.DataFrame(list(rows))
    if columns is not None:
        for column in columns:
            if column not in frame.columns:
                frame[column] = ""
        frame = frame[columns]
    frame.to_csv(output_path, index=False)


def append_note(existing: Any, note: str) -> str:
    existing_text = clean_value(existing)
    return f"{existing_text}; {note}" if existing_text else note


def business_status_is_active(value: Any) -> bool:
    text = clean_value(value).upper()
    return text in {"", "OPERATIONAL"}
