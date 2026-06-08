"""
Phoenix / Scottsdale 25-business sample builder for Upwork proof-of-work.

Purpose:
- Generate a clean sample CSV/XLSX for local businesses within the Phoenix metro area.
- Uses Google Places API (New) Text Search.
- Leaves restricted or unavailable fields transparent instead of fabricating data.

Setup:
1. Add GOOGLE_MAPS_API_KEY to .env
2. Run: python scripts/phoenix_25_sample.py
3. Output appears in exports/

Notes:
- Owner/executive name, fax, exact employee count, exact revenue, and year established are not consistently available from Google Places.
- This script creates source/confidence columns so the client can see what is verified vs. estimated/unavailable.
"""

from __future__ import annotations

import os
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
import requests
from dotenv import load_dotenv


# Scottsdale, AZ 85258 approximate center
SCOTTSDALE_85258_LAT = 33.5666
SCOTTSDALE_85258_LNG = -111.9004
RADIUS_METERS = 160_934  # approx 100 miles
TARGET_ROWS = 25

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Mix of SMB categories to show range without overfitting to one niche.
SEARCH_QUERIES = [
    "HVAC contractors near Scottsdale AZ",
    "plumbing companies near Scottsdale AZ",
    "commercial cleaning companies near Scottsdale AZ",
    "roofing contractors near Scottsdale AZ",
    "landscaping companies near Scottsdale AZ",
    "dentist offices near Scottsdale AZ",
    "medical spas near Scottsdale AZ",
    "auto repair shops near Scottsdale AZ",
    "accounting firms near Scottsdale AZ",
    "real estate agencies near Scottsdale AZ",
    "insurance agencies near Scottsdale AZ",
    "law firms near Scottsdale AZ",
    "restaurants near Scottsdale AZ",
    "fitness studios near Scottsdale AZ",
    "property management companies near Scottsdale AZ",
]

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.businessStatus",
        "places.types",
        "places.location",
    ]
)


CATEGORY_ESTIMATES = {
    "hvac": ("5-50", "$500K-$10M"),
    "plumber": ("5-50", "$500K-$10M"),
    "plumbing": ("5-50", "$500K-$10M"),
    "roofing": ("5-75", "$750K-$15M"),
    "landscaping": ("3-50", "$250K-$5M"),
    "cleaning": ("5-100", "$250K-$7M"),
    "dentist": ("5-30", "$500K-$5M"),
    "medical": ("5-50", "$500K-$8M"),
    "auto": ("3-25", "$300K-$4M"),
    "accounting": ("2-50", "$250K-$8M"),
    "real estate": ("2-100", "$250K-$20M"),
    "insurance": ("2-50", "$250K-$10M"),
    "law": ("2-100", "$500K-$20M"),
    "restaurant": ("10-75", "$500K-$8M"),
    "fitness": ("3-40", "$250K-$4M"),
    "property": ("3-100", "$500K-$20M"),
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_city_state_zip(formatted_address: str) -> Dict[str, str]:
    """Best-effort parser for US formatted addresses from Google Places."""
    result = {"street_address": "", "city": "", "state": "", "zip": ""}
    if not formatted_address:
        return result

    parts = [p.strip() for p in formatted_address.split(",")]
    if len(parts) >= 1:
        result["street_address"] = parts[0]
    if len(parts) >= 2:
        result["city"] = parts[1]
    if len(parts) >= 3:
        state_zip = parts[2].strip()
        match = re.search(r"\b([A-Z]{2})\s+(\d{5})(?:-\d{4})?\b", state_zip)
        if match:
            result["state"] = match.group(1)
            result["zip"] = match.group(2)
    return result


def infer_category(types: List[str], query: str) -> str:
    combined = " ".join(types or []) + " " + query
    combined = combined.lower().replace("_", " ")

    for key in CATEGORY_ESTIMATES.keys():
        if key in combined:
            return key.title()

    if types:
        return str(types[0]).replace("_", " ").title()
    return "Local Business"


def estimate_size_and_revenue(category: str) -> Dict[str, str]:
    category_lower = category.lower()
    for key, (employees, revenue) in CATEGORY_ESTIMATES.items():
        if key in category_lower:
            return {
                "employee_count": employees,
                "estimated_annual_revenue": revenue,
                "employee_revenue_confidence": "Low - category-based estimate for sample only",
            }
    return {
        "employee_count": "Unknown",
        "estimated_annual_revenue": "Unknown",
        "employee_revenue_confidence": "Unavailable from base source",
    }


def places_text_search(api_key: str, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    payload = {
        "textQuery": query,
        "maxResultCount": max_results,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": SCOTTSDALE_85258_LAT,
                    "longitude": SCOTTSDALE_85258_LNG,
                },
                "radius": RADIUS_METERS,
            }
        },
    }

    response = requests.post(
        PLACES_TEXT_SEARCH_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Google Places API error {response.status_code}: {response.text[:500]}"
        )

    return response.json().get("places", [])


def normalize_place(place: Dict[str, Any], query: str) -> Dict[str, str]:
    display_name = place.get("displayName", {}) or {}
    company_name = clean_text(display_name.get("text"))
    formatted_address = clean_text(place.get("formattedAddress"))
    address_parts = parse_city_state_zip(formatted_address)
    types = place.get("types", []) or []
    category = infer_category(types, query)
    estimates = estimate_size_and_revenue(category)

    return {
        "company_name": company_name,
        "owner_executive_first_name": "",
        "owner_executive_last_name": "",
        "street_address": address_parts["street_address"],
        "city": address_parts["city"],
        "state": address_parts["state"],
        "zip": address_parts["zip"],
        "phone_number": clean_text(place.get("nationalPhoneNumber")) or clean_text(place.get("internationalPhoneNumber")),
        "fax_number": "Unavailable from base source",
        "website_domain": clean_text(place.get("websiteUri")),
        "employee_count": estimates["employee_count"],
        "estimated_annual_revenue": estimates["estimated_annual_revenue"],
        "year_established": "Needs secondary-source enrichment",
        "business_category": category,
        "business_status": clean_text(place.get("businessStatus")),
        "google_place_id": clean_text(place.get("id")),
        "source_url": clean_text(place.get("googleMapsUri")),
        "source_query": query,
        "data_confidence_notes": estimates["employee_revenue_confidence"],
    }


def dedupe_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    clean_rows = []

    for row in rows:
        key = (
            row.get("google_place_id")
            or row.get("website_domain")
            or f"{row.get('company_name')}|{row.get('phone_number')}|{row.get('street_address')}"
        ).lower()

        if key in seen:
            continue
        seen.add(key)
        clean_rows.append(row)

    return clean_rows


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise SystemExit(
            "Missing GOOGLE_MAPS_API_KEY. Create a .env file with: GOOGLE_MAPS_API_KEY=your_key_here"
        )

    all_rows: List[Dict[str, str]] = []

    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        places = places_text_search(api_key, query=query, max_results=20)

        for place in places:
            row = normalize_place(place, query=query)
            if row["company_name"] and row["street_address"]:
                all_rows.append(row)

        all_rows = dedupe_rows(all_rows)
        print(f"Collected unique rows: {len(all_rows)}")

        if len(all_rows) >= TARGET_ROWS:
            break

        time.sleep(0.4)

    final_rows = dedupe_rows(all_rows)[:TARGET_ROWS]

    if not final_rows:
        raise SystemExit("No rows collected. Check API key, billing, and Places API access.")

    df = pd.DataFrame(final_rows)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = EXPORT_DIR / f"phoenix_scottsdale_25_business_sample_{timestamp}.csv"
    xlsx_path = EXPORT_DIR / f"phoenix_scottsdale_25_business_sample_{timestamp}.xlsx"

    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    print("\nDone.")
    print(f"CSV:  {csv_path}")
    print(f"XLSX: {xlsx_path}")
    print("\nImportant: review the file before sending. Do not overstate low-confidence estimates.")


if __name__ == "__main__":
    main()
