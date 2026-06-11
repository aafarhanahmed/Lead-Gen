from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from .config import DEFAULT_MAX_RESULTS_PER_QUERY, DEFAULT_SLEEP_SECONDS, require_google_places_key
from .places_client import PlacesClient
from .utils import clean_value, normalize_phone, normalize_url, now_utc, write_csv

OUTPUT_COLUMNS = [
    "place_id",
    "business_name",
    "website",
    "normalized_website",
    "website_status",
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
    "places_mode",
    "pulled_at",
    "lead_lane",
    "prospect_quality_score",
    "notes",
]


def main() -> int:
    args = parse_args()
    try:
        api_key = require_google_places_key()
        queries = load_queries(args)
        client = PlacesClient(
            api_key,
            cache_dir=args.cache_dir,
            use_cache=not args.no_cache,
            force_refresh=args.force_refresh,
            sleep_seconds=args.sleep_seconds,
        )
        rows: list[dict[str, Any]] = []
        for index, query in enumerate(queries, start=1):
            industry = clean_value(query["industry"])
            city = clean_value(query["city"])
            text_query = f"{industry} in {city}"
            print(f"[{index}/{len(queries)}] Places {args.mode}: {text_query}")
            places = client.text_search(text_query, max_results=args.max_results_per_query, mode=args.mode)
            for place in places:
                rows.append(place_to_row(place, industry, city, text_query, args.mode))
            print(f"  pulled {len(places)} result(s)")
        rows = dedupe_rows(rows)
        write_csv(rows, args.output, OUTPUT_COLUMNS)
        print(f"Wrote {len(rows)} raw lead(s): {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local business lead CSVs from Google Places Text Search.")
    parser.add_argument("--industry", help="Industry search term, e.g. plumber.")
    parser.add_argument("--city", help="City/region, e.g. Calgary AB.")
    parser.add_argument("--queries-file", help="CSV with industry,city columns.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--max-results-per-query", type=int, default=DEFAULT_MAX_RESULTS_PER_QUERY)
    parser.add_argument("--mode", choices=["enriched", "ids-only"], default="enriched")
    parser.add_argument("--cache-dir", default=".cache/places")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
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


def place_to_row(place: dict[str, Any], industry: str, city: str, source_query: str, mode: str) -> dict[str, Any]:
    display_name = place.get("displayName") if isinstance(place.get("displayName"), dict) else {}
    website = clean_value(place.get("websiteUri"))
    normalized_website = normalize_url(website)
    website_status = classify_website_status(website, mode)
    return {
        "place_id": clean_value(place.get("id") or place.get("name")),
        "business_name": clean_value(display_name.get("text") or place.get("name")),
        "website": website,
        "normalized_website": normalized_website,
        "website_status": website_status,
        "phone": normalize_phone(place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")),
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
        "places_mode": mode,
        "pulled_at": now_utc(),
        "lead_lane": "no_website_pitch" if website_status == "no_website_listed_on_google" else "website_review_pitch",
        "prospect_quality_score": prospect_quality_score(place, website_status),
        "notes": "",
    }


def classify_website_status(website: str, mode: str) -> str:
    if mode == "ids-only":
        return "website_unknown"
    return "has_website" if clean_value(website) else "no_website_listed_on_google"


def prospect_quality_score(place: dict[str, Any], website_status: str) -> int:
    score = 0
    rating = float(place.get("rating") or 0)
    reviews = int(place.get("userRatingCount") or 0)
    if website_status == "no_website_listed_on_google":
        score += 30
    if place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"):
        score += 20
    if reviews >= 20:
        score += 20
    elif reviews >= 10:
        score += 10
    if rating >= 4.2:
        score += 15
    if clean_value(place.get("businessStatus")).upper() in {"", "OPERATIONAL"}:
        score += 15
    return min(score, 100)


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("place_id"):
            key = f"place:{str(row['place_id']).lower()}"
        elif row.get("normalized_website"):
            key = f"web:{str(row['normalized_website']).lower()}"
        else:
            key = f"name-city:{str(row.get('business_name', '')).lower()}|{str(row.get('city', '')).lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
