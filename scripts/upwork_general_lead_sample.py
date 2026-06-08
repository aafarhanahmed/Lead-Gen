"""
General B2B/B2C lead generation sample builder for Upwork proposals.

Use for jobs where the client asks for accurate, qualified leads but has not yet provided
an exact ICP. The output is a client-safe 25-row CSV showing structure, formatting,
and base-record extraction. Deeper contact enrichment is intentionally withheld in
this free sample and should be completed only in the paid production run.

Setup:
1. Add GOOGLE_PLACES_API_KEY to .env
2. Run: python scripts/upwork_general_lead_sample.py
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

# Adjustable sample ICP. Change these when a client provides a specific target market.
SEARCH_CENTERS = [
    {"name": "Atlanta GA", "lat": 33.7490, "lng": -84.3880},
    {"name": "Dallas TX", "lat": 32.7767, "lng": -96.7970},
    {"name": "Phoenix AZ", "lat": 33.4484, "lng": -112.0740},
]

SEARCH_QUERIES = [
    "commercial cleaning companies",
    "property management companies",
    "HVAC contractors",
    "roofing contractors",
    "insurance agencies",
    "accounting firms",
    "IT services companies",
    "marketing agencies",
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


def parse_address(formatted_address: str) -> Dict[str, str]:
    result = {"street_address": "", "city": "", "state": "", "zip": ""}
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if len(parts) >= 1:
        result["street_address"] = parts[0]
    if len(parts) >= 2:
        result["city"] = parts[1]
    if len(parts) >= 3:
        match = re.search(r"\b([A-Z]{2})\s+(\d{5})(?:-\d{4})?\b", parts[2])
        if match:
            result["state"] = match.group(1)
            result["zip"] = match.group(2)
    return result


def category_from_query(query: str, types: List[str]) -> str:
    if query:
        return query.title()
    if types:
        return str(types[0]).replace("_", " ").title()
    return "Business"


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


def normalize(place: Dict[str, Any], query: str, center_name: str) -> Dict[str, str]:
    name = clean((place.get("displayName") or {}).get("text"))
    address = clean(place.get("formattedAddress"))
    parsed = parse_address(address)
    website = clean(place.get("websiteUri"))
    phone = clean(place.get("nationalPhoneNumber")) or clean(place.get("internationalPhoneNumber"))
    types = place.get("types", []) or []

    return {
        "company_name": name,
        "industry_or_category": category_from_query(query, types),
        "street_address": parsed["street_address"],
        "city": parsed["city"],
        "state": parsed["state"],
        "zip": parsed["zip"],
        "phone_number": phone,
        "website_domain": website,
        "decision_maker_first_name": "Withheld in free sample - available during paid enrichment where publicly sourced",
        "decision_maker_last_name": "Withheld in free sample - available during paid enrichment where publicly sourced",
        "decision_maker_title": "Withheld in free sample - target titles confirmed after ICP kickoff",
        "business_email": "Withheld in free sample - can be enriched and verified in paid run",
        "linkedin_profile_url": "Withheld in free sample - no restricted-platform scraping",
        "lead_fit_notes": f"Base record extracted for sample near {center_name}; ICP qualification/enrichment pending",
        "verification_status": "Base record extracted; contact verification pending paid run",
        "sample_note": "Sample demonstrates structure and extraction capability; final dataset can include verified contacts, emails, titles, and source/confidence notes where available.",
    }


def dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for row in rows:
        key = (row["website_domain"] or row["phone_number"] or f"{row['company_name']}|{row['street_address']}").lower()
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
                row = normalize(place, query, center["name"])
                if row["company_name"] and (row["phone_number"] or row["website_domain"]):
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
    out = EXPORT_DIR / f"upwork_general_lead_generation_25_sample_{timestamp}.csv"
    df.to_csv(out, index=False)
    print(f"Done: {out}")
    print("Review quickly, then attach this CSV as the sample for the generic lead generation job.")


if __name__ == "__main__":
    main()
