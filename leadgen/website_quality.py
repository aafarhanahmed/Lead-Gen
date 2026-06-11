from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .utils import append_note, clean_value, normalize_url, now_utc, read_csv, write_csv

USER_AGENT = "LocalBusinessLeadFinder/1.0"
CTA_RE = re.compile(r"book|quote|estimate|call|contact|schedule|request|get started|free consultation", re.I)
YEAR_RE = re.compile(r"(?:©|copyright)?\s*(20\d{2}|19\d{2})", re.I)


def main() -> int:
    args = parse_args()
    try:
        frame = read_csv(args.input)
        if args.limit is not None:
            frame = frame.head(args.limit)
        rows: list[dict[str, Any]] = []
        total = len(frame)
        for index, row in enumerate(frame.to_dict("records"), start=1):
            clean_row = {key: clean_value(value) for key, value in row.items()}
            website = clean_row.get("normalized_website") or clean_row.get("website")
            print(f"[{index}/{total}] Reviewing website signals: {clean_row.get('business_name') or website}")
            try:
                clean_row.update(review_homepage(website))
            except Exception as exc:
                clean_row["notes"] = append_note(clean_row.get("notes", ""), f"website_quality_error: {exc}")
                clean_row.update(empty_result(str(exc)))
            rows.append(clean_row)
            if args.sleep_seconds > 0 and index < total:
                time.sleep(args.sleep_seconds)
        write_csv(rows, args.output)
        print(f"Wrote website-quality rows: {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review public homepage signals for manual lead qualification.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    return parser.parse_args()


def review_homepage(website: str) -> dict[str, Any]:
    base_url = normalize_url(website)
    if not base_url:
        return empty_result("missing_website")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    started = time.time()
    response = session.get(base_url, timeout=15, allow_redirects=True)
    elapsed_ms = int((time.time() - started) * 1000)
    if response.status_code >= 400 or "text/html" not in response.headers.get("content-type", ""):
        return empty_result(f"homepage_fetch_failed_{response.status_code}")

    html = response.text[:500000]
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    lower_html = html.lower()

    final_url = response.url
    https_found = urlsplit(final_url).scheme == "https"
    mobile_viewport_found = bool(soup.find("meta", attrs={"name": re.compile("viewport", re.I)}))
    title_found = bool(soup.find("title") and soup.find("title").get_text(strip=True))
    meta_description_found = bool(soup.find("meta", attrs={"name": re.compile("description", re.I)}))
    form_found = bool(soup.find("form"))
    tel_link_found = "href=\"tel:" in lower_html or "href='tel:" in lower_html
    mailto_found = "href=\"mailto:" in lower_html or "href='mailto:" in lower_html
    contact_word_found = bool(re.search(r"contact|quote|booking|appointment|estimate", visible_text[:5000], re.I))
    cta_found = bool(CTA_RE.search(visible_text[:5000]))
    schema_found = "schema.org" in lower_html or "application/ld+json" in lower_html
    old_year = old_copyright_year(visible_text)

    outdated_signals: list[str] = []
    lead_capture_gaps: list[str] = []
    trust_gaps: list[str] = []

    if not https_found:
        outdated_signals.append("Website did not resolve to HTTPS")
    if not mobile_viewport_found:
        outdated_signals.append("No mobile viewport tag found")
    if old_year:
        outdated_signals.append(f"Old copyright year found: {old_year}")
    if elapsed_ms > 3500:
        outdated_signals.append(f"Homepage response looked slow in this run: {elapsed_ms} ms")
    if not title_found:
        trust_gaps.append("Missing or empty page title")
    if not meta_description_found:
        trust_gaps.append("Missing homepage meta description")
    if not schema_found:
        trust_gaps.append("No obvious schema/local business structured data detected")
    if not contact_word_found:
        lead_capture_gaps.append("No obvious contact/quote/booking wording near top of page")
    if not form_found:
        lead_capture_gaps.append("No form detected on homepage")
    if not tel_link_found:
        lead_capture_gaps.append("No click-to-call tel link detected")
    if not mailto_found:
        lead_capture_gaps.append("No mailto email link detected")
    if not cta_found:
        lead_capture_gaps.append("No clear call-to-action wording detected")

    score = 100 - (8 * len(outdated_signals)) - (7 * len(lead_capture_gaps)) - (4 * len(trust_gaps))
    score = max(0, min(100, score))

    return {
        "website_final_url": final_url,
        "website_quality_score": str(score),
        "outdated_signal_count": str(len(outdated_signals)),
        "outdated_signals": " | ".join(outdated_signals),
        "lead_capture_gaps": " | ".join(lead_capture_gaps),
        "trust_gaps": " | ".join(trust_gaps),
        "form_found": str(form_found),
        "tel_link_found": str(tel_link_found),
        "mailto_found": str(mailto_found),
        "mobile_viewport_found": str(mobile_viewport_found),
        "https_found": str(https_found),
        "old_copyright_year": str(old_year or ""),
        "homepage_response_ms": str(elapsed_ms),
        "scan_completed_at": now_utc(),
        "website_quality_error": "",
    }


def old_copyright_year(text: str) -> int | None:
    years = [int(match) for match in YEAR_RE.findall(text[-5000:])]
    if not years:
        return None
    newest = max(years)
    current = datetime.utcnow().year
    return newest if newest <= current - 5 else None


def empty_result(error: str = "") -> dict[str, Any]:
    return {
        "website_quality_score": "",
        "outdated_signal_count": "",
        "outdated_signals": "",
        "lead_capture_gaps": "",
        "trust_gaps": "",
        "form_found": "False",
        "tel_link_found": "False",
        "mailto_found": "False",
        "mobile_viewport_found": "False",
        "https_found": "",
        "old_copyright_year": "",
        "homepage_response_ms": "",
        "scan_completed_at": now_utc(),
        "website_quality_error": error,
    }


if __name__ == "__main__":
    raise SystemExit(main())
