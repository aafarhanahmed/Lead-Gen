from __future__ import annotations

import argparse
import sys
from typing import Any

from .config import BUSINESS_CONTACT_EMAIL, BUSINESS_NAME, BUSINESS_WEBSITE, OUTREACH_FROM_NAME, SAMPLE_REPORT_URL
from .utils import clean_value, now_utc, read_csv, write_csv


def main() -> int:
    args = parse_args()
    try:
        frame = read_csv(args.input)
        if args.limit is not None:
            frame = frame.head(args.limit)
        rows = [build_outreach_row({key: clean_value(value) for key, value in row.items()}) for row in frame.to_dict("records")]
        write_csv(rows, args.output)
        print(f"Wrote outreach queue: {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate manual-review outreach drafts. Does not send messages.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def build_outreach_row(row: dict[str, Any]) -> dict[str, Any]:
    business = clean_value(row.get("business_name")) or "your business"
    service = clean_value(row.get("recommended_service_1")) or "Free Website Diagnostic"
    price = clean_value(row.get("service_price_1"))
    lane = clean_value(row.get("lead_lane"))
    angle = clean_value(row.get("outreach_angle"))
    why = clean_value(row.get("why_this_service"))

    if lane == "no_website_pitch":
        subject = f"Quick note about {business}'s Google profile"
        body = no_website_email(business, row, service, price)
        phone = no_website_phone_opener(business)
        dm = no_website_dm(business)
    elif lane == "website_review_pitch":
        subject = f"Quick website observation for {business}"
        body = website_review_email(business, row, service, price)
        phone = website_phone_opener(business, service)
        dm = website_dm(business, row, service)
    else:
        subject = f"Quick note for {business}"
        body = soft_diagnostic_email(business, row)
        phone = soft_phone_opener(business)
        dm = soft_dm(business)

    row.update(
        {
            "subject": subject,
            "email_body": body,
            "phone_opener": phone,
            "linkedin_or_dm": dm,
            "outreach_status": "ready_for_manual_review",
            "unsubscribe_line": 'If this is not relevant, reply "no thanks" and I will not follow up.',
            "created_at": now_utc(),
            "internal_angle": angle,
            "internal_reason": why,
        }
    )
    return row


def no_website_email(business: str, row: dict[str, Any], service: str, price: str) -> str:
    city = clean_value(row.get("city"))
    industry = clean_value(row.get("industry"))
    context = f" while looking at {industry} businesses in {city}" if industry and city else ""
    price_line = f" The package I usually start with is {service} ({price})." if price else ""
    return (
        f"Hi {business},\n\n"
        f"I found your business on Google{context}. I may be wrong, but I did not see a website listed on your Google profile.\n\n"
        f"I run {BUSINESS_NAME}. I help local service businesses set up simple lead-ready websites with service sections, trust signals, mobile contact paths, and a clear inquiry form.{price_line}\n\n"
        "Would it be worth sending you a simple example of what I mean?\n\n"
        f"{OUTREACH_FROM_NAME}\n{BUSINESS_NAME}\n{BUSINESS_WEBSITE}\n{BUSINESS_CONTACT_EMAIL}\n\n"
        'If this is not relevant, reply "no thanks" and I will not follow up.'
    )


def website_review_email(business: str, row: dict[str, Any], service: str, price: str) -> str:
    observation = first_observation(row)
    price_line = f" The relevant fixed-scope service is usually {service} ({price})." if price else ""
    return (
        f"Hi {business},\n\n"
        f"I had a quick look at your public website and noticed: {observation}\n\n"
        f"I run {BUSINESS_NAME}. I help local businesses clean up website contact paths, trust signals, forms, and simple lead tracking so inquiries are easier to capture and follow up on.{price_line}\n\n"
        f"Here is the sample diagnostic format: {SAMPLE_REPORT_URL}\n\n"
        f"Would you like me to send over the top few fixes I would prioritize for {business}?\n\n"
        f"{OUTREACH_FROM_NAME}\n{BUSINESS_NAME}\n{BUSINESS_CONTACT_EMAIL}\n\n"
        'If this is not relevant, reply "no thanks" and I will not follow up.'
    )


def soft_diagnostic_email(business: str, row: dict[str, Any]) -> str:
    return (
        f"Hi {business},\n\n"
        f"I found {business} while researching local businesses and thought a quick website/profile diagnostic might be useful.\n\n"
        f"I run {BUSINESS_NAME}. I review visible contact paths, trust signals, and simple lead-capture friction for small businesses.\n\n"
        f"Sample format: {SAMPLE_REPORT_URL}\n\n"
        "Would you like me to run a free quick diagnostic?\n\n"
        f"{OUTREACH_FROM_NAME}\n{BUSINESS_NAME}\n{BUSINESS_CONTACT_EMAIL}\n\n"
        'If this is not relevant, reply "no thanks" and I will not follow up.'
    )


def first_observation(row: dict[str, Any]) -> str:
    for key in ("lead_capture_gaps", "outdated_signals", "trust_gaps", "why_this_service"):
        value = clean_value(row.get(key))
        if value:
            return value.split(" | ")[0].strip().rstrip(".") + "."
    return "there may be a few visible contact-path or trust-signal improvements worth reviewing."


def no_website_phone_opener(business: str) -> str:
    return (
        f"Hi, is this {business}? My name is {OUTREACH_FROM_NAME} from {BUSINESS_NAME}. "
        "I found the business on Google and may be wrong, but I did not see a website listed. "
        "Who would be the right person to send a simple example website layout to?"
    )


def website_phone_opener(business: str, service: str) -> str:
    return (
        f"Hi, is this {business}? My name is {OUTREACH_FROM_NAME} from {BUSINESS_NAME}. "
        f"I had a quick note about the website contact path. I am not calling to sell ads or SEO; I help with practical fixes like {service}. "
        "Who would be the right person to send the note to?"
    )


def soft_phone_opener(business: str) -> str:
    return f"Hi, is this {business}? My name is {OUTREACH_FROM_NAME} from {BUSINESS_NAME}. I had a quick website/profile diagnostic note. Who would be the right person to send it to?"


def no_website_dm(business: str) -> str:
    return f"Quick note — I found {business} on Google and may be wrong, but I did not see a website listed. I build simple lead-ready websites for local businesses. I can send a quick example if useful."


def website_dm(business: str, row: dict[str, Any], service: str) -> str:
    return f"Quick note — I looked at {business}'s public website and noticed: {first_observation(row)} I help local businesses with practical fixes like {service}. I can send a short sample diagnostic if useful."


def soft_dm(business: str) -> str:
    return f"Quick note — I run short website/profile diagnostics for local businesses. I can send a sample format for {business} if useful."


if __name__ == "__main__":
    raise SystemExit(main())
