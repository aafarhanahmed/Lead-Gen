"""Optional safe SendGrid sender for manually approved outreach."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

try:
    from lead_tools.config import (
        OUTREACH_FROM_EMAIL,
        OUTREACH_FROM_NAME,
        SENDGRID_API_KEY,
        SYSTEM_CURRENT_CONTACT_EMAIL,
    )
except ImportError:
    from config import OUTREACH_FROM_EMAIL, OUTREACH_FROM_NAME, SENDGRID_API_KEY, SYSTEM_CURRENT_CONTACT_EMAIL


REQUIRED_COLUMNS = ["email", "subject", "email_body", "outreach_status", "consent_basis", "do_not_contact_found"]
LOG_COLUMNS = ["sent_at", "business_name", "email", "subject", "status", "provider", "provider_message_id", "error"]
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def main() -> int:
    args = parse_args()
    frame = pd.read_csv(args.input, dtype=str).fillna("")
    validate_columns(frame)
    candidates = eligible_rows(frame)
    selected = candidates[: args.max_send]

    if not args.send:
        print("Dry run only. No emails will be sent.")
        for row_index, row in selected:
            print(f"Would send row {row_index + 1}: {row.get('business_name', '')} <{row.get('email', '')}>")
        print(f"Eligible rows found: {len(candidates)}. Max send this run: {args.max_send}.")
        return 0

    if not SENDGRID_API_KEY:
        print("Error: SENDGRID_API_KEY is required for real sending.", file=sys.stderr)
        return 2
    from_email = OUTREACH_FROM_EMAIL or SYSTEM_CURRENT_CONTACT_EMAIL
    if not from_email:
        print("Error: OUTREACH_FROM_EMAIL or SYSTEM_CURRENT_CONTACT_EMAIL is required.", file=sys.stderr)
        return 2

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for count, (row_index, row) in enumerate(selected, start=1):
        print(f"[{count}/{len(selected)}] Sending approved row {row_index + 1}: {row.get('email')}")
        log_row = send_one(row, from_email)
        append_log(log_path, log_row)
        if args.sleep_seconds > 0 and count < len(selected):
            time.sleep(args.sleep_seconds)
    print(f"Send log written to: {log_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely send manually approved outreach via SendGrid.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--max-send", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=10.0)
    parser.add_argument("--send", action="store_true", help="Actually send. Default is dry run.")
    return parser.parse_args()


def validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required column(s): {', '.join(missing)}")


def eligible_rows(frame: pd.DataFrame) -> list[tuple[int, dict[str, str]]]:
    rows: list[tuple[int, dict[str, str]]] = []
    for index, series in frame.iterrows():
        row = {column: clean_value(series.get(column, "")) for column in frame.columns}
        if row.get("outreach_status") != "approved_to_send":
            continue
        if is_true(row.get("do_not_contact_found")):
            continue
        if not row.get("email") or not row.get("consent_basis"):
            continue
        if not row.get("subject") or not row.get("email_body"):
            continue
        rows.append((index, row))
    return rows


def send_one(row: dict[str, str], from_email: str) -> dict[str, str]:
    payload = {
        "personalizations": [{"to": [{"email": row["email"]}], "subject": row["subject"]}],
        "from": {"email": from_email, "name": OUTREACH_FROM_NAME},
        "content": [{"type": "text/plain", "value": row["email_body"]}],
    }
    status = "sent"
    message_id = ""
    error = ""
    try:
        response = requests.post(
            SENDGRID_URL,
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        message_id = response.headers.get("X-Message-Id", "")
        if response.status_code >= 400:
            status = "error"
            error = response.text[:500]
    except requests.RequestException as exc:
        status = "error"
        error = str(exc)

    return {
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "business_name": row.get("business_name", ""),
        "email": row.get("email", ""),
        "subject": row.get("subject", ""),
        "status": status,
        "provider": "SendGrid",
        "provider_message_id": message_id,
        "error": error,
    }


def append_log(path: Path, row: dict[str, str]) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in LOG_COLUMNS})


def is_true(value: Any) -> bool:
    return clean_value(value).lower() in {"true", "1", "yes", "y"}


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
