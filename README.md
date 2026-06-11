# Lead-Gen — Standalone Local Business Lead Finder

A standalone Python tool for building local business prospect lists from the official Google Places API, with a strong focus on finding businesses that do **not** have a website displayed on Google Maps / Google Places.

Primary use case:

```text
Find local businesses with no website listed on Google → manually review → pitch a simple website build.
```

Secondary use case:

```text
Find local businesses with weak or outdated websites → manually review → pitch a lead-capture, form, profile, or website cleanup service.
```

This repo is designed to live locally inside a folder such as:

```text
Desktop/
  Python Automations/
    Lead-Gen/
```

## What this tool does

- Uses the official Google Places API Text Search endpoint.
- Builds CSV lead lists by industry and city.
- Labels businesses as:
  - `no_website_listed_on_google`
  - `has_website`
  - `website_unknown`
- Splits no-website leads from website-present leads.
- Scores basic prospect quality using rating, review count, phone availability, and operational status.
- Optionally scans public business websites for simple outdated / weak lead-capture signals.
- Matches each lead to a relevant service offer.
- Generates manual-review outreach drafts.

## What this tool does not do

- It does not scrape Google Maps HTML.
- It does not scrape LinkedIn.
- It does not bypass logins, paywalls, CAPTCHAs, admin pages, checkout pages, or private pages.
- It does not prove a business has no website anywhere on the internet.
- It does not automatically send emails.
- It does not guarantee replies, booked calls, rankings, revenue, or leads.

Important wording: `no_website_listed_on_google` means Google Places did not return a website URL for that business. It does **not** guarantee that the business has no website anywhere.

## Setup

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and add your key:

```text
GOOGLE_PLACES_API_KEY=your_key_here
```

## Fast first run — Calgary no-website leads

```bash
python -m leadgen.run_pipeline \
  --queries-file data/queries/calgary_home_services.csv \
  --batch-name calgary_home_services_001 \
  --max-results-per-query 20 \
  --mode no-website-first
```

Outputs are written to:

```text
outputs/lead_lists/
```

Expected files:

```text
calgary_home_services_001_raw.csv
calgary_home_services_001_clean.csv
calgary_home_services_001_no_website.csv
calgary_home_services_001_has_website.csv
calgary_home_services_001_service_matched.csv
calgary_home_services_001_outreach_queue.csv
```

## Cost-control defaults

Google Places can become expensive if you run huge batches without thinking. This tool is intentionally capped by default.

Recommended first sprint:

```text
5–10 queries per city
10–20 results per query
100–200 raw leads per run
manual review before outreach
```

Use narrow searches instead of broad ones.

Good:

```text
roofing contractor Calgary AB
emergency plumber Calgary AB
garage door repair Calgary AB
med spa Calgary AB
```

Weak:

```text
businesses in Canada
services near me
companies
```

## Main workflow

```text
industry + city CSV
→ Google Places lead sourcing
→ clean and dedupe
→ split no-website vs has-website
→ optional website-quality scan
→ service matching
→ manual-review outreach queue
```

## Services supported

The service matcher is built around this offer ladder:

| Signal | Suggested service |
|---|---|
| No website listed on Google | Lead-Ready Business Website — $799 CAD |
| Website exists but weak contact path | Lead Capture Fix — $499 CAD |
| Missing form / tracking / intake clarity | Form + Lead Tracker Setup — $299 CAD |
| Weak profile / trust basics | Google Profile / Trust Cleanup — $299 CAD |
| Not enough evidence yet | Free Website Diagnostic |
| Process / spreadsheet / workflow pain | Data & Workflow Automation — $150–$1,200 CAD |

## Manual review rules

Before contacting anyone, check:

- business is relevant and active;
- the tool's observation is true;
- no obvious franchise/corporate branch issue;
- no do-not-contact language;
- the outreach angle is honest;
- you have a relevant reason for contacting them.

Use this tool as lead intelligence and outreach preparation, not mass spam automation.

## Current package

Use the standalone package under:

```text
leadgen/
```

The older copied files under `src/lead_pipeline/` are legacy System Current-era files and should not be used for new runs.
