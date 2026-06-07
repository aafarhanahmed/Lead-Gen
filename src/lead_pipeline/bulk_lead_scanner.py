"""Bulk lead scanner CLI.

Run from internal-tools/system-current-audit-engine:
python lead_tools/bulk_lead_scanner.py --input lead_tools/sample_input.csv --output outputs/lead_lists/scored_leads.csv --limit 25
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from audit_engine.crawler import audit_website
from audit_engine.scoring import score_audit

try:
    from lead_tools.lead_score import calculate_lead_score
    from lead_tools.observation_writer import write_observation
except ImportError:
    from lead_score import calculate_lead_score
    from observation_writer import write_observation


REQUIRED_COLUMNS = ["business_name"]
OPTIONAL_COLUMNS = [
    "website",
    "normalized_website",
    "industry",
    "city",
    "phone",
    "google_rating",
    "review_count",
    "email",
    "place_id",
    "google_maps_uri",
    "formatted_address",
    "source_query",
    "source_api",
    "email_source_url",
    "consent_basis",
    "relevance_reason",
    "do_not_contact_found",
    "unsubscribe_status",
    "last_contacted_at",
    "outreach_status",
    "notes",
]
OUTPUT_COLUMNS = [
    "place_id",
    "business_name",
    "website",
    "normalized_website",
    "industry",
    "city",
    "formatted_address",
    "phone",
    "email",
    "google_maps_uri",
    "source_query",
    "source_api",
    "email_source_url",
    "consent_basis",
    "relevance_reason",
    "do_not_contact_found",
    "unsubscribe_status",
    "last_contacted_at",
    "outreach_status",
    "google_rating",
    "review_count",
    "fetch_ok",
    "audit_score",
    "audit_grade",
    "lead_score",
    "priority",
    "lead_reasons",
    "observation",
    "phone_detected",
    "tel_link_present",
    "email_detected",
    "contact_page_found",
    "cta_detected",
    "trust_detected",
    "meta_description_exists",
    "homepage_title",
    "top_gap",
    "recommended_offer",
    "suggested_next_action",
    "scan_completed_at",
    "error",
]


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    leads = pd.read_csv(input_path)
    _validate_columns(leads)
    if args.limit is not None:
        leads = leads.head(args.limit)

    total = len(leads)
    output_rows: list[dict] = []

    for index, row in leads.iterrows():
        clean_row = _normalize_row(row.to_dict())
        website = clean_row.get("website") or clean_row.get("normalized_website", "")
        clean_row["website"] = website
        business_name = clean_row.get("business_name", "")

        if not website:
            output_rows.append(_build_error_row(clean_row, "Missing website."))
            continue

        print(f"[{len(output_rows) + 1}/{total}] Scanning {business_name or 'Unnamed Business'} - {website}")

        try:
            raw = audit_website(website)
            scorecard = score_audit(raw)
            lead_score_result = calculate_lead_score(clean_row, raw, scorecard)
            observation = write_observation(raw, scorecard, lead_score_result)
            output_rows.append(
                _build_output_row(
                    clean_row,
                    raw,
                    scorecard,
                    lead_score_result,
                    observation,
                    error=raw.get("error") or "",
                )
            )
        except Exception as exc:
            output_rows.append(_build_error_row(clean_row, str(exc)))

        if args.sleep_seconds > 0 and len(output_rows) < total:
            time.sleep(args.sleep_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS).to_csv(output_path, index=False)
    print(f"Wrote scored leads to: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a CSV of website leads for manual outbound review.")
    parser.add_argument("--input", required=True, help="Path to input leads CSV.")
    parser.add_argument("--output", required=True, help="Path to output scored CSV.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of rows to scan.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Polite pause between website scans. Default: 1.0.",
    )
    return parser.parse_args()


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required column(s): {', '.join(missing)}")
    if "website" not in frame.columns and "normalized_website" not in frame.columns:
        raise ValueError("Input CSV must include either website or normalized_website.")


def _normalize_row(row: dict) -> dict:
    normalized = {}
    for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        normalized[column] = _clean_value(row.get(column, ""))
    return normalized


def _build_output_row(
    row: dict,
    raw: dict,
    scorecard: dict,
    lead_score_result: dict,
    observation: str,
    error: str = "",
) -> dict:
    lead_capture = _as_dict(raw.get("lead_capture"))
    trust_signals = _as_dict(raw.get("trust_signals"))
    phone_detected = bool(raw.get("phone_detected") or raw.get("phone_numbers") or lead_capture.get("phones"))
    email_detected = bool(raw.get("email_detected") or raw.get("emails") or lead_capture.get("emails"))
    cta_detected = bool(raw.get("cta_detected") or lead_capture.get("cta_buttons_sample") or lead_capture.get("cta_inventory"))
    trust_detected = bool(
        raw.get("trust_detected")
        or raw.get("trust_keywords_found")
        or trust_signals.get("trust_keywords_found")
        or trust_signals.get("review_platform_links")
        or trust_signals.get("social_links")
    )

    return _ordered_output(
        {
            "business_name": row.get("business_name", ""),
            "website": row.get("website", ""),
            "normalized_website": row.get("normalized_website", ""),
            "industry": row.get("industry", ""),
            "city": row.get("city", ""),
            "place_id": row.get("place_id", ""),
            "formatted_address": row.get("formatted_address", ""),
            "phone": row.get("phone", ""),
            "email": row.get("email", ""),
            "google_maps_uri": row.get("google_maps_uri", ""),
            "source_query": row.get("source_query", ""),
            "source_api": row.get("source_api", ""),
            "email_source_url": row.get("email_source_url", ""),
            "consent_basis": row.get("consent_basis", ""),
            "relevance_reason": row.get("relevance_reason", ""),
            "do_not_contact_found": row.get("do_not_contact_found", ""),
            "unsubscribe_status": row.get("unsubscribe_status", ""),
            "last_contacted_at": row.get("last_contacted_at", ""),
            "outreach_status": row.get("outreach_status", ""),
            "google_rating": row.get("google_rating", ""),
            "review_count": row.get("review_count", ""),
            "fetch_ok": bool(raw.get("fetch_ok")),
            "audit_score": scorecard.get("overall_score", ""),
            "audit_grade": scorecard.get("grade", ""),
            "lead_score": lead_score_result.get("lead_score", ""),
            "priority": lead_score_result.get("priority", ""),
            "lead_reasons": json.dumps(lead_score_result.get("lead_reasons", [])),
            "observation": observation,
            "phone_detected": phone_detected,
            "tel_link_present": bool(lead_capture.get("tel_link_present")),
            "email_detected": email_detected,
            "contact_page_found": bool(raw.get("contact_page_found")),
            "cta_detected": cta_detected,
            "trust_detected": trust_detected,
            "meta_description_exists": bool(raw.get("meta_description_exists")),
            "homepage_title": raw.get("title_text", ""),
            "top_gap": _extract_top_gap(scorecard, lead_score_result),
            "recommended_offer": _recommended_offer(lead_score_result.get("lead_score")),
            "suggested_next_action": _suggested_next_action(lead_score_result.get("lead_score")),
            "scan_completed_at": _timestamp(),
            "error": error,
        }
    )


def _build_error_row(row: dict, error: str) -> dict:
    return _ordered_output(
        {
            "business_name": row.get("business_name", ""),
            "website": row.get("website", ""),
            "normalized_website": row.get("normalized_website", ""),
            "industry": row.get("industry", ""),
            "city": row.get("city", ""),
            "place_id": row.get("place_id", ""),
            "formatted_address": row.get("formatted_address", ""),
            "phone": row.get("phone", ""),
            "email": row.get("email", ""),
            "google_maps_uri": row.get("google_maps_uri", ""),
            "source_query": row.get("source_query", ""),
            "source_api": row.get("source_api", ""),
            "email_source_url": row.get("email_source_url", ""),
            "consent_basis": row.get("consent_basis", ""),
            "relevance_reason": row.get("relevance_reason", ""),
            "do_not_contact_found": row.get("do_not_contact_found", ""),
            "unsubscribe_status": row.get("unsubscribe_status", ""),
            "last_contacted_at": row.get("last_contacted_at", ""),
            "outreach_status": row.get("outreach_status", ""),
            "google_rating": row.get("google_rating", ""),
            "review_count": row.get("review_count", ""),
            "fetch_ok": False,
            "audit_score": "",
            "audit_grade": "",
            "lead_score": "",
            "priority": "",
            "lead_reasons": json.dumps([]),
            "observation": "",
            "phone_detected": False,
            "tel_link_present": False,
            "email_detected": False,
            "contact_page_found": False,
            "cta_detected": False,
            "trust_detected": False,
            "meta_description_exists": False,
            "homepage_title": "",
            "top_gap": "",
            "recommended_offer": "Manual review",
            "suggested_next_action": "Skip unless manually relevant.",
            "scan_completed_at": _timestamp(),
            "error": error,
        }
    )


def _extract_top_gap(scorecard: dict, lead_score_result: dict) -> str:
    breakdown = scorecard.get("breakdown")
    if isinstance(breakdown, list) and breakdown:
        scored_categories = [
            item for item in breakdown
            if isinstance(item, dict) and _to_float(item.get("max_score")) > 0
        ]
        if scored_categories:
            lowest = min(
                scored_categories,
                key=lambda item: _to_float(item.get("score")) / _to_float(item.get("max_score")),
            )
            top_gap = _clean_value(lowest.get("top_gap", ""))
            if top_gap and top_gap != "No major gap detected in this category.":
                return top_gap

    reasons = lead_score_result.get("lead_reasons") or []
    if reasons:
        return str(reasons[0])
    return ""


def _ordered_output(values: dict) -> dict:
    return {column: values.get(column, "") for column in OUTPUT_COLUMNS}


def _recommended_offer(lead_score: Any) -> str:
    score = _to_float(lead_score)
    if score >= 60:
        return "Revenue Friction Diagnostic Pro"
    if score >= 35:
        return "Online Presence Diagnostic"
    return "Manual review"


def _suggested_next_action(lead_score: Any) -> str:
    score = _to_float(lead_score)
    if score >= 60:
        return "Send personalized observation-led email and consider phone follow-up."
    if score >= 35:
        return "Send light diagnostic message or save for later batch."
    return "Skip unless manually relevant."


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else 0.0
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    sys.exit(main())
