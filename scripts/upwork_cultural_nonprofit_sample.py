"""
Cultural nonprofit fundraising-contact sample builder for Upwork proposals.

Use for jobs targeting museums, symphonies, orchestras, performing arts centers,
and cultural institutions with donation/fundraising activity.

The output is a client-safe 25-row CSV using the client's required schema. Base
organization details and websites are extracted. Deeper person/email enrichment is
intentionally withheld in the free sample and should be completed in the paid run
through public websites, development/team pages, email verification, and manual QA.

Setup:
1. Add GOOGLE_PLACES_API_KEY to .env
2. Run: python scripts/upwork_cultural_nonprofit_sample.py
3. Output appears in exports/
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


TARGET_ROWS = 25
RADIUS_METERS = 50_000
EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

SEARCH_CENTERS = [
    {"name": "New York NY", "lat": 40.7128, "lng": -74.0060},
    {"name": "Chicago IL", "lat": 41.8781, "lng": -87.6298},
    {"name": "Los Angeles CA", "lat": 34.0522, "lng": -118.2437},
    {"name": "Boston MA", "lat": 42.3601, "lng": -71.0589},
]

SEARCH_QUERIES = [
    "art museums",
    "science museums",
    "children's museums",
    "history museums",
    "symphony orchestras",
    "performing arts centers",
    "opera companies",
    "ballet companies",
]

FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.types",
])

DONATION_KEYWORDS = [
    "donate",
    "support",
    "ways to give",
    "membership",
    "annual fund",
    "patron",
    "gala",
    "give",
]

COMMON_DONATION_PATHS = [
    "/donate",
    "/support",
    "/support-us",
    "/give",
    "/ways-to-give",
    "/membership",
    "/join-support",
]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def get_api_key() -> str:
    return os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY") or ""


def parse_address(formatted_address: str) -> Dict[str, str]:
    result = {"city": "", "state": ""}
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if len(parts) >= 2:
        result["city"] = parts[-3] if len(parts) >= 4 else parts[1]
    if len(parts) >= 3:
        match = re.search(r"\b([A-Z]{2})\s+\d{5}", parts[-2] if len(parts) >= 4 else parts[2])
        if match:
            result["state"] = match.group(1)
    return result


def org_type_from_query(query: str, types: List[str]) -> str:
    q = query.lower()
    if "symphony" in q or "orchestra" in q:
        return "Symphony / Orchestra"
    if "performing" in q:
        return "Performing Arts Center"
    if "opera" in q:
        return "Opera Company"
    if "ballet" in q:
        return "Ballet Company"
    if "museum" in q:
        return "Museum"
    if types:
        return str(types[0]).replace("_", " ").title()
    return "Cultural Institution"


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


def find_donation_page(website: str) -> Dict[str, str]:
    if not website:
        return {"donation_page_url": "", "evidence": "Donation evidence check pending paid/manual QA"}

    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadResearchSample/1.0)"}

    for path in COMMON_DONATION_PATHS:
        candidate = urljoin(website.rstrip("/") + "/", path.lstrip("/"))
        try:
            resp = requests.get(candidate, headers=headers, timeout=8, allow_redirects=True)
            if resp.status_code < 400:
                text = resp.text[:5000].lower()
                if any(keyword in text for keyword in DONATION_KEYWORDS):
                    return {"donation_page_url": resp.url, "evidence": "Donation/support page detected by public website check"}
        except requests.RequestException:
            pass

    try:
        resp = requests.get(website, headers=headers, timeout=8, allow_redirects=True)
        if resp.status_code < 400:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                label = clean(link.get_text(" ")).lower()
                href = clean(link.get("href"))
                combined = f"{label} {href}".lower()
                if any(keyword in combined for keyword in DONATION_KEYWORDS):
                    return {"donation_page_url": urljoin(resp.url, href), "evidence": f"Donation-related link found: {label[:60]}"}
    except requests.RequestException:
        pass

    return {"donation_page_url": "", "evidence": "Donation evidence check pending paid/manual QA"}


def normalize(place: Dict[str, Any], query: str) -> Dict[str, str]:
    org_name = clean((place.get("displayName") or {}).get("text"))
    website = clean(place.get("websiteUri"))
    address = clean(place.get("formattedAddress"))
    parsed = parse_address(address)
    org_type = org_type_from_query(query, place.get("types", []) or [])
    donation = find_donation_page(website)

    return {
        "organization_name": org_name,
        "organization_type": org_type,
        "website": website,
        "donation_page_url": donation["donation_page_url"],
        "evidence_of_donation_activity": donation["evidence"],
        "contact_first_name": "Withheld in free sample - available during paid enrichment where publicly sourced",
        "contact_last_name": "Withheld in free sample - available during paid enrichment where publicly sourced",
        "contact_title": "Target titles: Director of Development, Advancement, Membership, Donor Relations, Executive Director",
        "contact_email": "Withheld in free sample - can be enriched and verified in paid run",
        "contact_linkedin_url": "Withheld in free sample - no restricted-platform scraping",
        "organization_city": parsed["city"],
        "organization_state": parsed["state"],
        "notes": "Base organization extracted; donation/contact verification to be completed in paid run with manual QA",
        "source_url_for_contact_or_donation_evidence": donation["donation_page_url"] or website,
        "sample_note": "Sample demonstrates schema and base extraction capability; final list can include verified fundraising contacts, emails, and source notes where available.",
    }


def dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for row in rows:
        key = (row["website"] or row["organization_name"]).lower()
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
                if row["organization_name"] and row["website"]:
                    rows.append(row)
            rows = dedupe(rows)
            print(f"Collected unique rows: {len(rows)}")
            if len(rows) >= TARGET_ROWS:
                break
            time.sleep(0.4)
        if len(rows) >= TARGET_ROWS:
            break

    final_rows = dedupe(rows)[:TARGET_ROWS]
    if not final_rows:
        raise SystemExit("No rows generated. Check API key and Places API access.")

    df = pd.DataFrame(final_rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = EXPORT_DIR / f"upwork_cultural_nonprofit_25_sample_{timestamp}.csv"
    df.to_csv(out, index=False)
    print(f"Done: {out}")
    print("Attach this CSV for the GiveTech cultural nonprofit fundraising-contact job.")


if __name__ == "__main__":
    main()
