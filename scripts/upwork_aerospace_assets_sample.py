"""
Aerospace / technical B2B prospect-list sample builder for Upwork proposals.

Use for jobs asking for high-quality verified prospects in aerospace, geospatial,
industrial inspection, engineering, energy, agriculture, insurance, mapping, and
similar technical B2B markets.

The output is a client-safe 25-row CSV using the client's expected schema. Base
company records are populated. Person-level names, emails, LinkedIn URLs, and
verification are intentionally withheld in the free sample and should be completed
in the paid production run after ICP confirmation.

Setup:
1. Add GOOGLE_PLACES_API_KEY to .env
2. Run: python scripts/upwork_aerospace_assets_sample.py
3. Output appears in exports/
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from dotenv import load_dotenv


TARGET_ROWS = 25
RADIUS_METERS = 50_000
EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

SEARCH_CENTERS = [
    {"name": "Denver CO", "lat": 39.7392, "lng": -104.9903},
    {"name": "Dallas TX", "lat": 32.7767, "lng": -96.7970},
    {"name": "Houston TX", "lat": 29.7604, "lng": -95.3698},
    {"name": "Los Angeles CA", "lat": 34.0522, "lng": -118.2437},
    {"name": "Seattle WA", "lat": 47.6062, "lng": -122.3321},
]

SEARCH_QUERIES = [
    "aerospace companies",
    "geospatial companies",
    "aerial imagery companies",
    "drone inspection companies",
    "engineering services companies",
    "industrial inspection companies",
    "mapping services companies",
    "remote sensing companies",
]

FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.types",
])


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def get_api_key() -> str:
    return os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY") or ""


def parse_city_state(formatted_address: str) -> Dict[str, str]:
    result = {"location": "", "city": "", "state": ""}
    result["location"] = formatted_address
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if len(parts) >= 2:
        result["city"] = parts[-3] if len(parts) >= 4 else parts[1]
    if len(parts) >= 3:
        match = re.search(r"\b([A-Z]{2})\s+\d{5}", parts[-2] if len(parts) >= 4 else parts[2])
        if match:
            result["state"] = match.group(1)
    return result


def segment_from_query(query: str) -> str:
    q = query.lower()
    if "aerospace" in q:
        return "Aerospace / Aviation"
    if "geospatial" in q or "mapping" in q or "remote sensing" in q or "imagery" in q:
        return "Geospatial / Mapping / Remote Sensing"
    if "drone" in q:
        return "Drone / Aerial Inspection"
    if "industrial inspection" in q:
        return "Industrial Inspection"
    if "engineering" in q:
        return "Engineering Services"
    return "Technical B2B"


def recommended_titles(segment: str) -> str:
    if "Aerospace" in segment:
        return "Target titles: Director of Business Development, VP Sales, Program Manager, Asset Manager, Operations Director"
    if "Geospatial" in segment or "Drone" in segment:
        return "Target titles: BD Director, Geospatial Manager, Remote Sensing Lead, Operations Director, Founder/CEO"
    if "Inspection" in segment:
        return "Target titles: Inspection Manager, Operations Director, Asset Integrity Manager, BD Director"
    return "Target titles: Founder/CEO, VP Sales, BD Director, Operations Director, Procurement/Program Manager"


def text_search(api_key: str, query: str, center: Dict[str, Any]) -> List[Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    payload = {
        "textQuery": f"{query} near {center['name']}",
        "maxResultCount": 20,
        "locationBias": {
            "circle": {
                "center": {"latitude": center["lat"], "longitude": center["lng"]},
                "radius": RADIUS_METERS,
            }
        },
    }
    response = requests.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Google Places API error {response.status_code}: {response.text[:400]}")
    return response.json().get("places", [])


def normalize(place: Dict[str, Any], query: str) -> Dict[str, str]:
    company = clean((place.get("displayName") or {}).get("text"))
    address = clean(place.get("formattedAddress"))
    parsed = parse_city_state(address)
    phone = clean(place.get("nationalPhoneNumber")) or clean(place.get("internationalPhoneNumber"))
    website = clean(place.get("websiteUri"))
    segment = segment_from_query(query)

    return {
        "full_name": "Withheld in free sample - available during paid contact enrichment where publicly sourced",
        "job_title": recommended_titles(segment),
        "company": company,
        "email": "Withheld in free sample - can be enriched and verified in paid run",
        "phone_if_available": phone,
        "linkedin_url": "Withheld in free sample - no restricted-platform scraping",
        "location": parsed["location"],
        "city": parsed["city"],
        "state": parsed["state"],
        "industry_segment": segment,
        "company_website": website,
        "source_notes": "Base company record extracted; ICP fit, contact names, emails, verification, and segmentation to be completed in paid run",
        "verification_status": "Base company found; email/contact verification pending paid run",
        "sample_note": "Sample demonstrates schema and base technical-market extraction capability; final list can include verified decision-makers, emails, tags, and source/confidence notes where available.",
    }


def dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for row in rows:
        key = (row["company_website"] or row["phone_if_available"] or row["company"]).lower()
        if key and key not in seen:
            seen.add(key)
            output.append(row)
    return output


def main() -> None:
    load_dotenv()
    api_key = get_api_key()
    if not api_key:
        raise SystemExit("Missing API key. Add GOOGLE_PLACES_API_KEY to .env")

    rows: List[Dict[str, str]] = []
    for center in SEARCH_CENTERS:
        for query in SEARCH_QUERIES:
            print(f"Searching: {query} near {center['name']}")
            places = text_search(api_key, query, center)
            for place in places:
                row = normalize(place, query)
                if row["company"] and (row["company_website"] or row["phone_if_available"]):
                    rows.append(row)
            rows = dedupe(rows)
            print(f"Collected unique rows: {len(rows)}")
            if len(rows) >= TARGET_ROWS:
                break
            time.sleep(0.3)
        if len(rows) >= TARGET_ROWS:
            break

    final_rows = dedupe(rows)[:TARGET_ROWS]
    if not final_rows:
        raise SystemExit("No rows generated. Check API key and Places API access.")

    df = pd.DataFrame(final_rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = EXPORT_DIR / f"upwork_aerospace_assets_25_sample_{timestamp}.csv"
    df.to_csv(out, index=False)
    print(f"Done: {out}")
    print("Attach this CSV for the aerospace/technical B2B prospect-list job.")


if __name__ == "__main__":
    main()
