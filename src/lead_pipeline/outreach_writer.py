"""Generate manual-review outreach drafts from scored leads."""

from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from lead_tools.config import SYSTEM_CURRENT_CONTACT_EMAIL, SYSTEM_CURRENT_SAMPLE_REPORT_URL
except ImportError:
    from config import SYSTEM_CURRENT_CONTACT_EMAIL, SYSTEM_CURRENT_SAMPLE_REPORT_URL


OUTPUT_COLUMNS = [
    "business_name",
    "website",
    "email",
    "city",
    "industry",
    "priority",
    "lead_score",
    "recommended_offer",
    "subject",
    "email_body",
    "linkedin_dm",
    "phone_opener",
    "observation",
    "sample_report_url",
    "consent_basis",
    "relevance_reason",
    "do_not_contact_found",
    "unsubscribe_line",
    "last_contacted_at",
    "outreach_status",
    "created_at",
]


def main() -> int:
    args = parse_args()
    frame = pd.read_csv(args.input, dtype=str).fillna("")
    if args.limit is not None:
        frame = frame.head(args.limit)
    rows = [build_outreach_row(series.to_dict()) for _, series in frame.iterrows()]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=OUTPUT_COLUMNS).to_csv(output_path, index=False)
    print(f"Wrote {len(rows)} outreach queue row(s) to: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate outreach drafts. Does not send emails.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def build_outreach_row(row: dict[str, Any]) -> dict[str, str]:
    business_name = clean_value(row.get("business_name")) or "your business"
    observation = clean_value(row.get("observation")) or (
        "I found a few public-facing website and lead-path improvements that may be worth reviewing."
    )
    priority = clean_value(row.get("priority"))
    lead_score = clean_value(row.get("lead_score"))
    recommended_offer = clean_value(row.get("recommended_offer")) or offer_for_score(lead_score)
    email = clean_value(row.get("email"))
    do_not_contact = is_true(row.get("do_not_contact_found"))
    unsubscribe_line = 'If this is not relevant, reply "no thanks" and I will not follow up.'
    outreach_status = status_for_row(priority, email, do_not_contact)
    subject = subject_for_business(business_name)
    body = ""
    if outreach_status != "do_not_contact":
        body = email_body(business_name, observation, priority, unsubscribe_line)

    return ordered(
        {
            "business_name": business_name,
            "website": clean_value(row.get("website")),
            "email": email,
            "city": clean_value(row.get("city")),
            "industry": clean_value(row.get("industry")),
            "priority": priority,
            "lead_score": lead_score,
            "recommended_offer": recommended_offer,
            "subject": subject,
            "email_body": body,
            "linkedin_dm": linkedin_dm(business_name, observation),
            "phone_opener": phone_opener(business_name),
            "observation": observation,
            "sample_report_url": SYSTEM_CURRENT_SAMPLE_REPORT_URL,
            "consent_basis": clean_value(row.get("consent_basis")),
            "relevance_reason": clean_value(row.get("relevance_reason")),
            "do_not_contact_found": str(do_not_contact),
            "unsubscribe_line": unsubscribe_line,
            "last_contacted_at": clean_value(row.get("last_contacted_at")),
            "outreach_status": outreach_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def email_body(business_name: str, observation: str, priority: str, unsubscribe_line: str) -> str:
    offer_line = ""
    if priority.lower() == "high":
        offer_line = "\n\nFor high-friction cases, I usually package this as the $199 Pro Diagnostic."
    return (
        f"Hi {business_name},\n\n"
        f"I had a quick look at {business_name} and noticed: {observation}\n\n"
        "I run System Current, a diagnostic-first online presence studio for small businesses. "
        "The diagnostic shows where a website or public online presence may be losing trust, calls, "
        "quote requests, or bookings before the owner spends more on ads, SEO, or a redesign."
        f"{offer_line}\n\n"
        "Here is the sample report format:\n"
        f"{SYSTEM_CURRENT_SAMPLE_REPORT_URL}\n\n"
        f"Would you like me to run this for {business_name} this week?\n\n"
        "Farhan\n"
        "System Current\n"
        f"{SYSTEM_CURRENT_CONTACT_EMAIL}\n\n"
        f"{unsubscribe_line}"
    )


def linkedin_dm(business_name: str, observation: str) -> str:
    return (
        f"Hey {business_name} - quick note. I looked at {business_name} and noticed {observation}\n\n"
        "I run short online presence diagnostics for small businesses so owners know what to fix "
        "before spending more on ads, SEO, or a redesign.\n\n"
        "I can send the sample report if useful."
    )


def phone_opener(business_name: str) -> str:
    return (
        f"Hi, is this {business_name}? My name is Farhan from System Current. I had a quick note "
        "about your website/contact path. I am not calling to sell a full website - I run a short "
        "diagnostic that shows what may be hurting calls, quote requests, or trust before businesses "
        "spend on ads or redesigns. Who would be the right person to send the sample report to?"
    )


def subject_for_business(business_name: str) -> str:
    if business_name and business_name != "your business":
        return f"Quick observation for {business_name}"
    return "Quick note on your website"


def status_for_row(priority: str, email: str, do_not_contact: bool) -> str:
    if do_not_contact:
        return "do_not_contact"
    if not email:
        return "needs_email_or_manual_channel"
    if priority.lower() == "low":
        return "low_priority_review"
    return "ready_for_manual_review"


def offer_for_score(value: str) -> str:
    score = to_float(value)
    if score >= 60:
        return "Revenue Friction Diagnostic Pro"
    if score >= 35:
        return "Online Presence Diagnostic"
    return "Manual review"


def ordered(values: dict[str, str]) -> dict[str, str]:
    return {column: values.get(column, "") for column in OUTPUT_COLUMNS}


def is_true(value: Any) -> bool:
    return clean_value(value).lower() in {"true", "1", "yes", "y"}


def to_float(value: Any) -> float:
    try:
        text = clean_value(value)
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
