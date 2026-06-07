from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = "SystemCurrentLeadResearch/1.0 (+https://systemcurrent.com)"
EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.+-])", re.I)

DO_NOT_CONTACT_TRUE = {"true", "1", "yes", "y"}
BAD_EMAIL_PARTS = [
    "example.com",
    "test@",
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
]


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_true(value) -> bool:
    return clean(value).lower() in DO_NOT_CONTACT_TRUE


def normalize_url(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    return text


def is_bad_email(email: str) -> bool:
    lower = clean(email).lower()
    if not lower or "@" not in lower:
        return True
    return any(part in lower for part in BAD_EMAIL_PARTS)


def fetch_html(url: str) -> str:
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
            allow_redirects=True,
        )
    except requests.RequestException:
        return ""
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400 or "text/html" not in content_type:
        return ""
    return response.text[:750_000]


def email_visible_in_html(email: str, html: str) -> tuple[bool, str]:
    if not email or not html:
        return False, ""

    target = email.lower().strip()
    soup = BeautifulSoup(html, "html.parser")

    # 1. Best case: explicit mailto.
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip().lower()
        if href.startswith("mailto:"):
            mailto_email = href.split(":", 1)[1].split("?", 1)[0].strip()
            if mailto_email == target:
                return True, "visible_mailto"

    # 2. Visible text only. This avoids hidden guessed/generated values where possible.
    visible_text = soup.get_text(" ", strip=True)
    visible_emails = {match.lower().strip() for match in EMAIL_RE.findall(visible_text)}
    if target in visible_emails:
        return True, "visible_text"

    return False, ""


def candidate_source_urls(row: dict[str, str]) -> list[str]:
    urls = []

    email_source_url = normalize_url(row.get("email_source_url", ""))
    website = normalize_url(row.get("website", ""))

    if email_source_url:
        urls.append(email_source_url)

    # Fallback candidates if source URL was not preserved properly.
    if website:
        urls.extend([
            website,
            urljoin(website.rstrip("/") + "/", "contact"),
            urljoin(website.rstrip("/") + "/", "contact-us"),
            urljoin(website.rstrip("/") + "/", "about"),
        ])

    seen = set()
    unique = []
    for url in urls:
        key = url.rstrip("/")
        if key and key not in seen:
            seen.add(key)
            unique.append(url)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    if args.max_rows:
        df = df.head(args.max_rows)

    send_rows = []
    skipped = []

    for i, series in df.iterrows():
        row = {col: clean(series.get(col, "")) for col in df.columns}
        email = row.get("email", "")

        reason = ""
        verified = False
        verified_source_url = ""

        if is_bad_email(email):
            reason = "missing_or_bad_email"
        elif is_true(row.get("do_not_contact_found", "")):
            reason = "do_not_contact_found"
        elif not row.get("consent_basis", ""):
            reason = "missing_consent_basis"
        else:
            for url in candidate_source_urls(row):
                html = fetch_html(url)
                ok, method = email_visible_in_html(email, html)
                if ok:
                    verified = True
                    verified_source_url = url
                    reason = method
                    break
            if not verified:
                reason = "email_not_visible_on_source_pages"

        row["email_verified_visible"] = str(verified)
        row["email_verification_reason"] = reason
        row["verified_email_source_url"] = verified_source_url

        if verified:
            # Make this the only file used for outbound.
            row["outreach_status"] = "approved_to_send"
            send_rows.append(row)
        else:
            row["outreach_status"] = "skip_no_visible_email"
            skipped.append(row)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(send_rows).to_csv(out_path, index=False)

    skipped_path = out_path.with_name(out_path.stem + "_skipped.csv")
    pd.DataFrame(skipped).to_csv(skipped_path, index=False)

    print(f"Input rows: {len(df)}")
    print(f"Send-ready visible-email rows: {len(send_rows)}")
    print(f"Skipped rows: {len(skipped)}")
    print(f"Send-ready CSV: {out_path}")
    print(f"Skipped CSV: {skipped_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
