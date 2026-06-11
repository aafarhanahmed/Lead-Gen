from __future__ import annotations

import argparse
import sys
from typing import Any

from .utils import business_status_is_active, clean_value, read_csv, to_float, to_int, write_csv


def main() -> int:
    args = parse_args()
    try:
        frame = read_csv(args.input)
        no_website_rows: list[dict[str, Any]] = []
        has_website_rows: list[dict[str, Any]] = []
        skipped_rows: list[dict[str, Any]] = []

        for row in frame.to_dict("records"):
            normalized = {key: clean_value(value) for key, value in row.items()}
            if not passes_quality_filters(normalized, args):
                normalized["split_status"] = "skipped_quality_filter"
                skipped_rows.append(normalized)
                continue
            if normalized.get("website_status") == "no_website_listed_on_google":
                normalized["lead_lane"] = "no_website_pitch"
                normalized["recommended_service_1"] = "Lead-Ready Business Website"
                normalized["service_price_1"] = "$799 CAD"
                normalized["outreach_angle"] = "No website displayed on Google profile"
                normalized["split_status"] = "selected_no_website"
                no_website_rows.append(normalized)
            elif normalized.get("website_status") == "has_website":
                normalized["lead_lane"] = "website_review_pitch"
                normalized["split_status"] = "selected_has_website"
                has_website_rows.append(normalized)
            else:
                normalized["split_status"] = "skipped_website_unknown"
                skipped_rows.append(normalized)

        write_csv(no_website_rows, args.no_website_output)
        write_csv(has_website_rows, args.has_website_output)
        if args.skipped_output:
            write_csv(skipped_rows, args.skipped_output)
        print(f"No-website leads: {len(no_website_rows)} → {args.no_website_output}")
        print(f"Has-website leads: {len(has_website_rows)} → {args.has_website_output}")
        if args.skipped_output:
            print(f"Skipped leads: {len(skipped_rows)} → {args.skipped_output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split clean leads into no-website and has-website files.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--no-website-output", required=True)
    parser.add_argument("--has-website-output", required=True)
    parser.add_argument("--skipped-output")
    parser.add_argument("--min-reviews", type=int, default=0)
    parser.add_argument("--min-rating", type=float, default=0.0)
    parser.add_argument("--require-phone", action="store_true")
    parser.add_argument("--operational-only", action="store_true", default=True)
    return parser.parse_args()


def passes_quality_filters(row: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.operational_only and not business_status_is_active(row.get("business_status")):
        return False
    if args.require_phone and not clean_value(row.get("phone")):
        return False
    if to_int(row.get("review_count")) < args.min_reviews:
        return False
    if to_float(row.get("google_rating")) < args.min_rating:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
