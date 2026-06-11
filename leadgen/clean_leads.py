from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

from .utils import clean_value, normalize_phone, normalize_text, normalize_url, now_utc, read_csv, write_csv


def main() -> int:
    args = parse_args()
    try:
        frame = read_csv(args.input)
        cleaned = clean_frame(frame)
        write_csv(cleaned.to_dict("records"), args.output)
        print(f"Wrote {len(cleaned)} clean lead(s): {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean and dedupe local business lead CSVs.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, series in frame.iterrows():
        row = {column: clean_value(series.get(column, "")) for column in frame.columns}
        for column in ("business_name", "industry", "city", "formatted_address"):
            if column in row:
                row[column] = normalize_text(row[column])
        if "phone" in row:
            row["phone"] = normalize_phone(row["phone"])
        website = row.get("website") or row.get("normalized_website", "")
        row["normalized_website"] = normalize_url(website)
        if row.get("website"):
            row["website"] = normalize_url(row["website"])
        row["website_status"] = classify_website_status(row)
        row["lead_lane"] = classify_lead_lane(row)
        row["duplicate_key"] = duplicate_key(row)
        row["cleaned_at"] = now_utc()
        key = row["duplicate_key"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return pd.DataFrame(rows)


def classify_website_status(row: dict[str, Any]) -> str:
    existing = clean_value(row.get("website_status"))
    if existing:
        return existing
    if clean_value(row.get("normalized_website") or row.get("website")):
        return "has_website"
    return "no_website_listed_on_google"


def classify_lead_lane(row: dict[str, Any]) -> str:
    if row.get("website_status") == "no_website_listed_on_google":
        return "no_website_pitch"
    if row.get("website_status") == "has_website":
        return "website_review_pitch"
    return "manual_review"


def duplicate_key(row: dict[str, Any]) -> str:
    place_id = clean_value(row.get("place_id")).lower()
    if place_id:
        return f"place:{place_id}"
    website = clean_value(row.get("normalized_website")).lower().rstrip("/")
    if website:
        return f"web:{website}"
    return f"name-city:{clean_value(row.get('business_name')).lower()}|{clean_value(row.get('city')).lower()}"


if __name__ == "__main__":
    raise SystemExit(main())
