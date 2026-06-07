"""Configuration helpers for internal lead tools."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


ENGINE_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(ENGINE_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")


GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
OUTREACH_FROM_EMAIL = os.getenv("OUTREACH_FROM_EMAIL", "").strip()
OUTREACH_FROM_NAME = os.getenv("OUTREACH_FROM_NAME", "Farhan").strip() or "Farhan"
SYSTEM_CURRENT_WEBSITE_URL = (
    os.getenv("SYSTEM_CURRENT_WEBSITE_URL", "https://systemcurrent.com").strip()
    or "https://systemcurrent.com"
)
SYSTEM_CURRENT_SAMPLE_REPORT_URL = (
    os.getenv("SYSTEM_CURRENT_SAMPLE_REPORT_URL", "https://systemcurrent.com/proof").strip()
    or "https://systemcurrent.com/proof"
)
SYSTEM_CURRENT_CONTACT_EMAIL = (
    os.getenv("SYSTEM_CURRENT_CONTACT_EMAIL", "hello@systemcurrent.com").strip()
    or "hello@systemcurrent.com"
)

DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_MAX_RESULTS_PER_QUERY = 20


def get_required_env(name: str) -> str:
    """Return a non-empty environment variable or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            "Add it to your shell environment or lead_tools/.env."
        )
    return value
