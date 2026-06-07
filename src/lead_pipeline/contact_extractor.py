"""Extract public contact emails from lead websites."""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from lead_tools.config import DEFAULT_SLEEP_SECONDS
except ImportError:
    from config import DEFAULT_SLEEP_SECONDS


USER_AGENT = "SystemCurrentLeadResearch/1.0 (+https://systemcurrent.com)"
EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.+-])", re.I)
LIKELY_LINK_RE = re.compile(r"contact|about|get-in-touch", re.I)
DO_NOT_CONTACT_PHRASES = (
    "do not contact",
    "no solicitation",
    "no solicitations",
    "no marketing emails",
    "do not email",
)
SKIP_PATH_PARTS = (
    "login",
    "admin",
    "wp-admin",
    "cart",
    "checkout",
    "account",
    "privacy",
    "terms",
)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    frame = pd.read_csv(input_path, dtype=str).fillna("")
    if args.limit is not None:
        frame = frame.head(args.limit)

    rows: list[dict[str, Any]] = []
    total = len(frame)
    for index, series in frame.iterrows():
        row = {column: clean_value(series.get(column, "")) for column in frame.columns}
        website = row.get("normalized_website") or row.get("website", "")
        print(f"[{len(rows) + 1}/{total}] Checking contact info for {row.get('business_name') or website}")
        try:
            row.update(extract_contact_fields(website))
        except Exception as exc:
            row.setdefault("email", "")
            row.setdefault("email_source_url", "")
            row["contact_page_url"] = ""
            row["email_confidence"] = ""
            row["do_not_contact_found"] = ""
            row.setdefault("consent_basis", "")
            row.setdefault("relevance_reason", "")
            row["notes"] = append_note(row.get("notes", ""), f"contact_extractor_error: {exc}")
        rows.append(row)
        if args.sleep_seconds > 0 and len(rows) < total:
            time.sleep(args.sleep_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Wrote enriched lead(s) to: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find public business emails from lead websites.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    return parser.parse_args()


def extract_contact_fields(website: str) -> dict[str, str]:
    base_url = normalize_url(website)
    if not base_url:
        return empty_contact_fields()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    urls = build_candidate_urls(base_url)
    pages: list[tuple[str, str]] = []
    robots = load_robots(session, base_url)

    for url in urls:
        if is_skipped_url(url) or not can_fetch(robots, url):
            continue
        html = fetch_html(session, url)
        if html:
            pages.append((url, html))
            if len(pages) == 1:
                urls.extend(discover_contact_links(base_url, html))
        if len(pages) >= 4:
            break

    found_emails: list[tuple[str, str]] = []
    do_not_contact_found = False
    contact_page_url = ""
    for url, html in pages:
        lower_html = html.lower()
        if any(phrase in lower_html for phrase in DO_NOT_CONTACT_PHRASES):
            do_not_contact_found = True
        if url != base_url and not contact_page_url:
            contact_page_url = url
        for email in extract_emails(html):
            found_emails.append((email, url))

    email, source_url = choose_email(found_emails)
    consent_basis = ""
    relevance_reason = ""
    if email and not do_not_contact_found:
        consent_basis = (
            "Business email was publicly listed on the company's website; "
            "manual relevance review required before outreach."
        )
        relevance_reason = (
            "System Current offers online presence diagnostics relevant to this business "
            "website and public lead path."
        )

    return {
        "email": email,
        "email_source_url": source_url,
        "contact_page_url": contact_page_url or source_url,
        "email_confidence": "high" if email and source_url.startswith(base_url.rstrip("/")) else ("medium" if email else ""),
        "do_not_contact_found": str(bool(do_not_contact_found)),
        "consent_basis": consent_basis,
        "relevance_reason": relevance_reason,
        "contact_extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def empty_contact_fields() -> dict[str, str]:
    return {
        "email": "",
        "email_source_url": "",
        "contact_page_url": "",
        "email_confidence": "",
        "do_not_contact_found": "",
        "consent_basis": "",
        "relevance_reason": "",
        "contact_extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def build_candidate_urls(base_url: str) -> list[str]:
    return unique_urls(
        [
            base_url,
            urljoin(base_url, "/contact"),
            urljoin(base_url, "/contact-us"),
            urljoin(base_url, "/about"),
        ]
    )


def discover_contact_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    base_host = urlsplit(base_url).netloc.lower()
    for anchor in soup.find_all("a", href=True):
        text = f"{anchor.get_text(' ', strip=True)} {anchor.get('href', '')}"
        if not LIKELY_LINK_RE.search(text):
            continue
        url = urljoin(base_url, anchor["href"])
        if urlsplit(url).netloc.lower() == base_host:
            urls.append(strip_fragment(url))
    return unique_urls(urls)[:3]


def fetch_html(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, timeout=12, allow_redirects=True)
    except requests.RequestException:
        return ""
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400 or "text/html" not in content_type:
        return ""
    return response.text[:500_000]


def extract_emails(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    emails: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("mailto:"):
            emails.add(href.split(":", 1)[1].split("?", 1)[0].strip())
    visible_text = soup.get_text(" ", strip=True)
    for email in EMAIL_RE.findall(visible_text):
        emails.add(email.strip())
    return [email for email in sorted(emails) if is_usable_email(email)]


def choose_email(found: list[tuple[str, str]]) -> tuple[str, str]:
    if not found:
        return "", ""
    sorted_found = sorted(found, key=lambda pair: email_rank(pair[0]))
    return sorted_found[0]


def email_rank(email: str) -> tuple[int, str]:
    local = email.split("@", 1)[0].lower()
    preferred = ("info", "hello", "contact", "office", "admin", "service", "sales")
    if local in preferred:
        return (0, email)
    return (1, email)


def is_usable_email(email: str) -> bool:
    lower = email.lower().strip(".;,)")
    bad_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    bad_locals = {"example", "test", "name", "email", "yourname", "you"}
    if lower.endswith(bad_suffixes) or "@example.com" in lower:
        return False
    if lower.split("@", 1)[0] in bad_locals:
        return False
    return True


def load_robots(session: requests.Session, base_url: str) -> RobotFileParser | None:
    robots_url = urljoin(base_url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = session.get(robots_url, timeout=8)
        if response.status_code >= 400:
            return None
        parser.parse(response.text.splitlines())
        return parser
    except Exception:
        return None


def can_fetch(parser: RobotFileParser | None, url: str) -> bool:
    if parser is None:
        return True
    try:
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def is_skipped_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(part in path for part in SKIP_PATH_PARTS)


def normalize_url(value: str) -> str:
    text = clean_value(value)
    if not text:
        return ""
    if not re.match(r"^https?://", text, flags=re.I):
        text = f"https://{text}"
    parts = urlsplit(text)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", ""))


def strip_fragment(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        clean = strip_fragment(url)
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def append_note(existing: str, note: str) -> str:
    return f"{existing}; {note}" if existing else note


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
