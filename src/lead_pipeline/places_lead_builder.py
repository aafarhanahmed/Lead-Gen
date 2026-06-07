"""Build raw lead CSVs using the official Google Places API."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

try:
    from lead_tools.config import (
        DEFAULT_MAX_RESULTS_PER_QUERY,
        DEFAULT_SLEEP_SECONDS,
        get_required_env,
    )
except ImportError:
    from config import DEFAULT_MAX_RESULTS_PER_QUERY, DEFAULT_SLEEP_SECONDS, get_required_env


PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.rating",
        "places.userRatingCount",
        "places.googleMapsUri",
        "places.businessStatus",
        "places.primaryType",
        "places.types",
        "nextPageToken",
    ]
)

OUTPUT_COLUMNS = [
    "place_id",
    "business_name",
    "website",
    "phone",
    "industry",
    "city",
    "formatted_address",
    "google_rating",
    "review_count",
    "google_maps_uri",
    "business_status",
    "primary_type",
    "types",
    "source_query",
    "source_api",
    "pulled_at",
    "email",
    "email_source_url",
    "consent_basis",
    "relevance_reason",
    "do_not_contact_found",
    "unsubscribe_status",
    "last_contacted_at",
    "outreach_status",
    "notes",
]


def main() -> int:
    args = parse_args()
    try:
        api_key = get_required_env("GOOGLE_PLACES_API_KEY")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    queries = load_queries(args)
    if not queries:
        print("No queries to run.", file=sys.stderr)
        return 1

    max_per_query = args.max_results_per_query or args.max_results or DEFAULT_MAX_RESULTS_PER_QUERY
    rows: list[dict[str, Any]] = []

    for index, query in enumerate(queries, start=1):
        industry = clean_value(query.get("industry"))
        city = clean_value(query.get("city"))
        text_query = f"{industry} in {city}".strip()
        print(f"[{index}/{len(queries)}] Searching Places API: {text_query}")
        try:
            rows.extend(fetch_places_query(api_key, industry, city, max_per_query))
        except Exception as exc:
            print(f"  Error for '{text_query}': {exc}", file=sys.stderr)
        if args.sleep_seconds > 0 and index < len(queries):
            time.sleep(args.sleep_seconds)

    deduped = dedupe_rows(rows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(deduped, columns=OUTPUT_COLUMNS).to_csv(output_path, index=False)
    print(f"Wrote {len(deduped)} raw lead(s) to: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build raw lead CSVs from Google Places Text Search.")
    parser.add_argument("--industry", help="Industry search term, e.g. plumber.")
    parser.add_argument("--city", help="City/region, e.g. Vancouver BC.")
    parser.add_argument("--queries-file", help="CSV with industry,city columns.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--max-results", type=int, default=None, help="Max results for a single query.")
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=None,
        help="Max results per query when using --queries-file.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    return parser.parse_args()


def load_queries(args: argparse.Namespace) -> list[dict[str, str]]:
    if args.queries_file:
        with Path(args.queries_file).open(newline="", encoding="utf-8") as handle:
            return [
                {"industry": row.get("industry", ""), "city": row.get("city", "")}
                for row in csv.DictReader(handle)
                if clean_value(row.get("industry")) and clean_value(row.get("city"))
            ]
    if args.industry and args.city:
        return [{"industry": args.industry, "city": args.city}]
    raise ValueError("Provide either --industry and --city, or --queries-file.")


def fetch_places_query(api_key: str, industry: str, city: str, max_results: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_token = ""
    pulled_at = datetime.now(timezone.utc).isoformat()
    source_query = f"{industry} in {city}".strip()

    while len(rows) < max_results:
        remaining = max_results - len(rows)
        payload: dict[str, Any] = {
            "textQuery": source_query,
            "maxResultCount": min(20, max(1, remaining)),
        }
        if page_token:
            payload["pageToken"] = page_token

        response = requests.post(
            PLACES_TEXT_SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            print(f"  Places API error {response.status_code}: {response.text[:500]}", file=sys.stderr)
            break

        data = response.json()
        places = data.get("places") or []
        for place in places:
            rows.append(place_to_row(place, industry, city, source_query, pulled_at))
            if len(rows) >= max_results:
                break

        page_token = clean_value(data.get("nextPageToken"))
        if not page_token or not places:
            break
        time.sleep(2.0)

    print(f"  Pulled {len(rows)} result(s).")
    return rows


def place_to_row(place: dict[str, Any], industry: str, city: str, source_query: str, pulled_at: str) -> dict[str, Any]:
    display_name = place.get("displayName") if isinstance(place.get("displayName"), dict) else {}
    return ordered_row(
        {
            "place_id": clean_value(place.get("id")),
            "business_name": clean_value(display_name.get("text")),
            "website": clean_value(place.get("websiteUri")),
            "phone": clean_value(place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")),
            "industry": industry,
            "city": city,
            "formatted_address": clean_value(place.get("formattedAddress")),
            "google_rating": clean_value(place.get("rating")),
            "review_count": clean_value(place.get("userRatingCount")),
            "google_maps_uri": clean_value(place.get("googleMapsUri")),
            "business_status": clean_value(place.get("businessStatus")),
            "primary_type": clean_value(place.get("primaryType")),
            "types": "|".join(place.get("types") or []),
            "source_query": source_query,
            "source_api": "Google Places API Text Search",
            "pulled_at": pulled_at,
            "email": "",
            "email_source_url": "",
            "consent_basis": "",
            "relevance_reason": "",
            "do_not_contact_found": "",
            "unsubscribe_status": "",
            "last_contacted_at": "",
            "outreach_status": "",
            "notes": "",
        }
    )


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = ""
        if clean_value(row.get("place_id")):
            key = f"place:{clean_value(row.get('place_id')).lower()}"
        elif clean_value(row.get("website")):
            key = f"web:{clean_value(row.get('website')).lower().rstrip('/')}"
        else:
            key = f"name-city:{clean_value(row.get('business_name')).lower()}|{clean_value(row.get('city')).lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ordered_row(row))
    return deduped


def ordered_row(values: dict[str, Any]) -> dict[str, Any]:
    return {column: values.get(column, "") for column in OUTPUT_COLUMNS}


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
