"""Clean and dedupe raw lead CSVs."""

from __future__ import annotations

import argparse
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "igshid"}


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    frame = pd.read_csv(input_path, dtype=str).fillna("")
    cleaned = clean_frame(frame)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False)
    print(f"Wrote {len(cleaned)} clean lead(s) to: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean and dedupe lead CSVs before scanning.")
    parser.add_argument("--input", required=True, help="Input raw lead CSV.")
    parser.add_argument("--output", required=True, help="Output clean lead CSV.")
    return parser.parse_args()


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()

    for _, series in frame.iterrows():
        row = {column: clean_value(series.get(column, "")) for column in frame.columns}
        for column in ("business_name", "city", "industry"):
            if column in row:
                row[column] = normalize_text(row[column])
        if "phone" in row:
            row["phone"] = normalize_phone(row["phone"])
        website = row.get("website") or row.get("normalized_website", "")
        normalized_website = normalize_website(website)
        row["website"] = normalize_website(row.get("website", "")) if row.get("website") else row.get("website", "")
        row["normalized_website"] = normalized_website
        duplicate_key = build_duplicate_key(row)
        row["duplicate_key"] = duplicate_key
        row["cleaned_at"] = now

        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        rows.append(row)

    return pd.DataFrame(rows)


def build_duplicate_key(row: dict[str, Any]) -> str:
    place_id = clean_value(row.get("place_id")).lower()
    if place_id:
        return f"place:{place_id}"
    normalized_website = clean_value(row.get("normalized_website")).lower()
    if normalized_website:
        return f"web:{normalized_website}"
    return (
        "name-city:"
        f"{clean_value(row.get('business_name')).lower()}|{clean_value(row.get('city')).lower()}"
    )


def normalize_website(value: str) -> str:
    text = clean_value(value)
    if not text:
        return ""
    if not re.match(r"^https?://", text, flags=re.IGNORECASE):
        text = f"https://{text}"
    parts = urlsplit(text)
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def normalize_phone(value: str) -> str:
    text = clean_value(value)
    return re.sub(r"\s+", " ", text)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", clean_value(value)).strip()


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
