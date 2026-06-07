"""Outbound lead scoring helpers.

This module is intentionally separate from the client-facing audit score.
The score here is only for internal outbound sales qualification.
"""

from __future__ import annotations

import math
from typing import Any


def calculate_lead_score(row: dict, raw: dict, scorecard: dict) -> dict:
    """
    Return:
    {
      "lead_score": int,
      "priority": "High" | "Medium" | "Low",
      "lead_reasons": list[str]
    }
    """
    lead_score = 0
    reasons: list[str] = []

    lead_capture = _as_dict(raw.get("lead_capture"))
    trust_signals = _as_dict(raw.get("trust_signals"))

    if _has_text(row.get("website")) and raw.get("fetch_ok"):
        lead_score += 10
        reasons.append("Website was reachable.")

    if _to_float(row.get("review_count")) >= 20:
        lead_score += 15
        reasons.append("Google review count is 20 or higher.")

    if _to_float(row.get("google_rating")) >= 4.2:
        lead_score += 10
        reasons.append("Google rating is 4.2 or higher.")

    if not _cta_detected(raw, lead_capture):
        lead_score += 20
        reasons.append("No clear CTA detected.")

    if _phone_detected(raw, lead_capture) and not lead_capture.get("tel_link_present"):
        lead_score += 15
        reasons.append("Phone detected but no click-to-call link found.")

    if not raw.get("contact_page_found"):
        lead_score += 15
        reasons.append("No contact page found.")

    if not _email_detected(raw, lead_capture):
        lead_score += 5
        reasons.append("No email detected.")

    if not _trust_detected(raw, trust_signals):
        lead_score += 15
        reasons.append("Weak or missing trust signals.")

    if not raw.get("meta_description_exists"):
        lead_score += 5
        reasons.append("Homepage meta description is missing.")

    if _to_float(scorecard.get("overall_score")) < 70:
        lead_score += 10
        reasons.append("Overall audit score is below 70.")

    return {
        "lead_score": int(lead_score),
        "priority": _priority(lead_score),
        "lead_reasons": reasons,
    }


def _priority(score: int) -> str:
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _has_text(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return bool(str(value).strip())


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else 0.0
    except (TypeError, ValueError):
        return 0.0


def _cta_detected(raw: dict, lead_capture: dict) -> bool:
    return bool(
        raw.get("cta_detected")
        or lead_capture.get("cta_buttons_sample")
        or lead_capture.get("cta_inventory")
    )


def _phone_detected(raw: dict, lead_capture: dict) -> bool:
    return bool(
        raw.get("phone_detected")
        or raw.get("phone_numbers")
        or lead_capture.get("phones")
    )


def _email_detected(raw: dict, lead_capture: dict) -> bool:
    return bool(
        raw.get("email_detected")
        or raw.get("emails")
        or lead_capture.get("emails")
    )


def _trust_detected(raw: dict, trust_signals: dict) -> bool:
    return bool(
        raw.get("trust_detected")
        or raw.get("trust_keywords_found")
        or trust_signals.get("trust_keywords_found")
        or trust_signals.get("review_platform_links")
        or trust_signals.get("social_links")
    )

