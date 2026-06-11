from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
DEFAULT_OUTPUT_DIR = os.getenv("DEFAULT_OUTPUT_DIR", "outputs/lead_lists").strip() or "outputs/lead_lists"
PLACES_CACHE_DIR = os.getenv("PLACES_CACHE_DIR", ".cache/places").strip() or ".cache/places"

OUTREACH_FROM_NAME = os.getenv("OUTREACH_FROM_NAME", "Farhan").strip() or "Farhan"
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "System Current").strip() or "System Current"
BUSINESS_WEBSITE = os.getenv("BUSINESS_WEBSITE", "https://systemcurrent.com").strip() or "https://systemcurrent.com"
BUSINESS_CONTACT_EMAIL = (
    os.getenv("BUSINESS_CONTACT_EMAIL", "hello@systemcurrent.com").strip() or "hello@systemcurrent.com"
)
SAMPLE_REPORT_URL = os.getenv("SAMPLE_REPORT_URL", "https://systemcurrent.com/proof").strip() or "https://systemcurrent.com/proof"

DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_MAX_RESULTS_PER_QUERY = 20


def require_google_places_key() -> str:
    if not GOOGLE_PLACES_API_KEY:
        raise RuntimeError(
            "Missing GOOGLE_PLACES_API_KEY. Add it to .env in the Lead-Gen repo root."
        )
    return GOOGLE_PLACES_API_KEY
