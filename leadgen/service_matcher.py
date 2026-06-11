from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

from .utils import clean_value, read_csv, to_float, to_int, write_csv

SERVICES = {
    "free_diagnostic": ("Free Website Diagnostic", "Free"),
    "profile_cleanup": ("Google Profile / Trust Cleanup", "$299 CAD"),
    "form_tracker": ("Form + Lead Tracker Setup", "$299 CAD"),
    "lead_capture_fix": ("Lead Capture Fix", "$499 CAD"),
    "website_build": ("Lead-Ready Business Website", "$799 CAD"),
    "workflow_automation": ("Data & Workflow Automation", "$150–$1,200 CAD"),
}


def main() -> int:
    args = parse_args()
    try:
        frames = [read_csv(args.input)]
        for path in args.append_input or []:
            frames.append(read_csv(path))
        frame = pd.concat(frames, ignore_index=True).fillna("") if len(frames) > 1 else frames[0]
        rows = [match_services({key: clean_value(value) for key, value in row.items()}) for row in frame.to_dict("records")]
        write_csv(rows, args.output)
        print(f"Wrote service-matched leads: {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match leads to best-fit service offers.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--append-input", action="append", default=[])
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def match_services(row: dict[str, Any]) -> dict[str, Any]:
    website_status = clean_value(row.get("website_status"))
    review_count = to_int(row.get("review_count"))
    rating = to_float(row.get("google_rating"))
    quality_score = to_float(row.get("website_quality_score")) if row.get("website_quality_score") else 0.0
    lead_capture_gaps = clean_value(row.get("lead_capture_gaps"))
    outdated_signals = clean_value(row.get("outdated_signals"))
    trust_gaps = clean_value(row.get("trust_gaps"))

    if website_status == "no_website_listed_on_google":
        primary = "website_build"
        secondary = "profile_cleanup" if review_count >= 10 else "free_diagnostic"
        confidence = "high" if review_count >= 20 and rating >= 4.2 and clean_value(row.get("phone")) else "medium"
        angle = "No website displayed on Google profile"
        why = "Google Places did not return a website URL. Manual review should confirm whether the business truly lacks a website before pitching a build."
        lane = "no_website_pitch"
    elif website_status == "has_website":
        if lead_capture_gaps:
            primary = "lead_capture_fix"
            secondary = "form_tracker"
            angle = "Existing website has visible contact-path gaps"
            why = f"Homepage review found: {lead_capture_gaps}"
            confidence = "high" if quality_score and quality_score < 70 else "medium"
        elif outdated_signals:
            primary = "lead_capture_fix"
            secondary = "profile_cleanup"
            angle = "Existing website shows outdated or weak technical signals"
            why = f"Homepage review found: {outdated_signals}"
            confidence = "medium"
        elif trust_gaps:
            primary = "profile_cleanup"
            secondary = "free_diagnostic"
            angle = "Public trust/profile consistency cleanup"
            why = f"Homepage review found: {trust_gaps}"
            confidence = "medium"
        else:
            primary = "free_diagnostic"
            secondary = "lead_capture_fix"
            angle = "Soft diagnostic-first outreach"
            why = "Website exists, but the tool did not find enough strong evidence for a hard pitch."
            confidence = "low"
        lane = "website_review_pitch"
    else:
        primary = "free_diagnostic"
        secondary = ""
        angle = "Manual review required"
        why = "Website status is unknown."
        confidence = "low"
        lane = "manual_review"

    primary_name, primary_price = SERVICES[primary]
    secondary_name, secondary_price = SERVICES[secondary] if secondary else ("", "")

    row.update(
        {
            "lead_lane": lane,
            "recommended_service_1": primary_name,
            "service_price_1": primary_price,
            "recommended_service_2": secondary_name,
            "service_price_2": secondary_price,
            "outreach_angle": angle,
            "why_this_service": why,
            "service_match_confidence": confidence,
            "manual_review_required": "True",
        }
    )
    return row


if __name__ == "__main__":
    raise SystemExit(main())
