# System Current Lead Tools — Operating Guide

This guide explains how to operate the internal lead-generation and outreach-preparation tools in `internal-tools/system-current-audit-engine/lead_tools/`.

The lead tools are intentionally separate from the paid audit fulfillment app. They should help System Current build lead lists, qualify prospects, identify website friction, and prepare manual outreach drafts without modifying the main website, checkout, Stripe, Streamlit app, or audit deliverable pipeline.

---

## 1. What this system does

The lead tools support this workflow:

```text
industry + city
→ Google Places API lead sourcing
→ raw leads CSV
→ clean and dedupe
→ public contact email extraction
→ website scan using the existing audit engine
→ lead score
→ specific observation
→ outreach draft queue
→ manual review
→ optional approved email sending
```

The system is designed to help you find businesses that may be good prospects for System Current's diagnostic products:

- Online Presence Diagnostic — $99 CAD
- Revenue Friction Diagnostic Pro — $199 CAD
- Private implementation/Quick Fix follow-up after diagnostic delivery

---

## 2. What this system does not do

It does **not**:

- scrape Google Maps HTML
- scrape LinkedIn
- bypass logins, paywalls, admin panels, checkout pages, or CAPTCHA
- submit forms
- send emails by default
- guarantee replies, leads, rankings, revenue, or appointments
- replace manual review
- change the Streamlit audit fulfillment flow
- change the public website
- change Stripe/payment code

---

## 3. Folder layout

```text
internal-tools/system-current-audit-engine/
├── audit_engine/                 # Existing paid audit engine — do not modify for lead ops
├── lead_tools/
│   ├── config.py
│   ├── places_lead_builder.py
│   ├── clean_leads.py
│   ├── contact_extractor.py
│   ├── bulk_lead_scanner.py
│   ├── lead_score.py
│   ├── observation_writer.py
│   ├── outreach_writer.py
│   ├── send_outreach.py
│   ├── run_lead_pipeline.py
│   ├── sample_input.csv
│   ├── queries.csv
│   ├── .env.example
│   ├── README.md
│   └── OPERATING_GUIDE.md
└── outputs/
    └── lead_lists/               # Generated CSVs — keep local, do not commit
```

Generated lead files should stay under:

```text
internal-tools/system-current-audit-engine/outputs/lead_lists/
```

This folder should remain ignored locally through `.git/info/exclude`.

---

## 4. Required setup

Run from the audit engine folder:

```bash
cd /workspaces/systemcurrent/internal-tools/system-current-audit-engine
source venv/bin/activate
```

If `.env.example` exists, copy it:

```bash
cp lead_tools/.env.example .env
```

Add your local secrets to `.env`:

```text
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
SENDGRID_API_KEY=
OUTREACH_FROM_EMAIL=
OUTREACH_FROM_NAME=Farhan
SYSTEM_CURRENT_WEBSITE_URL=https://systemcurrent.com
SYSTEM_CURRENT_SAMPLE_REPORT_URL=https://systemcurrent.com/proof
SYSTEM_CURRENT_CONTACT_EMAIL=hello@systemcurrent.com
```

Minimum required for the Places lead sourcing step:

```text
GOOGLE_PLACES_API_KEY
```

Do not commit `.env`.

---

## 5. API cost model

### Google Places API

The main paid dependency is Google Places API. The local scanner, cleaner, contact extractor, and outreach writer do not require paid APIs.

Current Google Maps Platform global pricing is SKU-based, priced per 1,000 billable events. Google lists a free usage cap for Places API Text Search Pro and then charges after the free cap. At the time this guide was written, the public pricing page listed:

- Places API Text Search Essentials (IDs Only): unlimited free usage
- Places API Text Search Pro: 5,000 free usage cap, then $32 per 1,000 events in the first paid tier
- Places API Place Details Pro: 5,000 free usage cap, then $17 per 1,000 events in the first paid tier

Official pricing page:

https://developers.google.com/maps/billing-and-pricing/pricing

Important: actual billing depends on which fields the script requests. Requesting richer fields such as website, phone, rating, and review count may trigger a higher SKU than ID-only search.

Practical launch-budget guidance:

```text
Safe test run:        2–5 queries, max 10–20 results each
Daily manual sprint:  5–10 queries, max 20 results each
Budget cap:           set billing alerts at $5, $10, and $25
```

Because Text Search commonly returns limited paginated result sets, scale by running multiple focused city/industry queries instead of one broad query.

Example:

```csv
industry,city
plumber,Vancouver BC
plumber,Burnaby BC
HVAC,Surrey BC
electrician,Richmond BC
dentist,Vancouver BC
physiotherapist,Burnaby BC
```

### SendGrid

SendGrid is optional. The lead tools are dry-run by default and do not require SendGrid unless you intentionally use real sending.

At the time this guide was written, Twilio SendGrid listed:

- Free Trial: $0/month for 60 days
- Essentials: starting at $19.95/month
- Pro: starting at $89.95/month

Official pricing page:

https://www.twilio.com/en-us/products/email-api/pricing

For the current System Current sprint, manual Gmail/LinkedIn outreach is preferred. Only use `send_outreach.py` after manual review and tiny approved batches.

---

## 6. Recommended first run

Start small. Do not run a huge batch first.

```bash
venv/bin/python lead_tools/run_lead_pipeline.py \
  --queries-file lead_tools/queries.csv \
  --batch-name test_001 \
  --max-results-per-query 10 \
  --scan-limit 20 \
  --sleep-seconds 1.5
```

Expected outputs:

```text
outputs/lead_lists/test_001_raw.csv
outputs/lead_lists/test_001_clean.csv
outputs/lead_lists/test_001_enriched.csv
outputs/lead_lists/test_001_scored.csv
outputs/lead_lists/test_001_outreach_queue.csv
```

---

## 7. Individual commands

### 7.1 Build raw leads from Google Places

```bash
venv/bin/python lead_tools/places_lead_builder.py \
  --industry "plumber" \
  --city "Vancouver BC" \
  --output outputs/lead_lists/raw_plumbers_vancouver.csv \
  --max-results 40
```

Batch mode:

```bash
venv/bin/python lead_tools/places_lead_builder.py \
  --queries-file lead_tools/queries.csv \
  --output outputs/lead_lists/raw_batch_001.csv \
  --max-results-per-query 20
```

### 7.2 Clean and dedupe leads

```bash
venv/bin/python lead_tools/clean_leads.py \
  --input outputs/lead_lists/raw_batch_001.csv \
  --output outputs/lead_lists/clean_batch_001.csv
```

### 7.3 Extract public contact emails

```bash
venv/bin/python lead_tools/contact_extractor.py \
  --input outputs/lead_lists/clean_batch_001.csv \
  --output outputs/lead_lists/enriched_batch_001.csv \
  --limit 50 \
  --sleep-seconds 1.0
```

### 7.4 Scan websites and score leads

```bash
venv/bin/python lead_tools/bulk_lead_scanner.py \
  --input outputs/lead_lists/enriched_batch_001.csv \
  --output outputs/lead_lists/scored_batch_001.csv \
  --limit 100 \
  --sleep-seconds 1.5
```

### 7.5 Generate outreach drafts

```bash
venv/bin/python lead_tools/outreach_writer.py \
  --input outputs/lead_lists/scored_batch_001.csv \
  --output outputs/lead_lists/outreach_queue_batch_001.csv \
  --limit 50
```

### 7.6 Optional dry-run email sender

Dry run only:

```bash
venv/bin/python lead_tools/send_outreach.py \
  --input outputs/lead_lists/outreach_queue_batch_001.csv \
  --log outputs/lead_lists/outreach_send_log.csv \
  --max-send 5
```

Real send requires all safeguards:

```bash
venv/bin/python lead_tools/send_outreach.py \
  --input outputs/lead_lists/outreach_queue_batch_001.csv \
  --log outputs/lead_lists/outreach_send_log.csv \
  --max-send 5 \
  --send
```

Real sending should only occur when:

- `SENDGRID_API_KEY` is set
- row has `outreach_status = approved_to_send`
- row has nonblank `email`
- row has nonblank `consent_basis`
- row has `do_not_contact_found` not true
- you manually reviewed the lead

---

## 8. Daily operating workflow

### Morning — build lead supply

Run 3–5 focused query combinations.

Good first niches:

```text
plumbers
HVAC companies
electricians
roofers
dentists
physiotherapists
chiropractors
med spas
contractors
```

Good first cities:

```text
Vancouver BC
Burnaby BC
Surrey BC
Richmond BC
Coquitlam BC
Calgary AB
Edmonton AB
Victoria BC
```

### Midday — review scored leads

Open:

```text
outputs/lead_lists/<batch>_scored.csv
```

Sort by:

```text
priority = High
lead_score = highest
review_count = highest
```

Pick the top 10–20.

### Afternoon — manual quality check

For each selected lead:

1. Open the website.
2. Confirm the observation is true.
3. Check the business is still active.
4. Check whether the email/contact method is appropriate.
5. Confirm no do-not-contact language.
6. Send manually or mark as approved only after review.

### Outreach target

Start with:

```text
10 high-quality manual messages per day
```

Then scale to:

```text
20–40 messages per day
5–10 phone follow-ups per day
```

---

## 9. CSV review checklist

Before outreach, review these columns:

```text
business_name
website
email
phone
google_rating
review_count
audit_score
lead_score
priority
recommended_offer
suggested_next_action
observation
consent_basis
relevance_reason
do_not_contact_found
outreach_status
```

Good lead profile:

```text
High lead_score
20+ reviews
rating above 4.2
real website
clear observation
email/contact method available
no do-not-contact language
business service is relevant to System Current
```

Bad lead profile:

```text
no website
inactive business
franchise/corporate branch with no local decision-maker
observation is generic or false
no relevant contact channel
low review count and low commercial value
```

---

## 10. Outreach rules

Use the system to prepare outreach, not to spam.

Every message should have:

- a specific observation
- a relevant reason for contacting
- a sample report link
- a clear opt-out line
- no guarantees
- no fake claims
- no mention of internal tools or AI

Do not say:

```text
guaranteed leads
guaranteed revenue
guaranteed SEO ranking
we scraped your data
AI generated audit
cheap audit
```

Use:

```text
public-facing diagnostic
online presence diagnostic
revenue friction
trust leakage
lead path
priority fixes
sample report
```

---

## 11. Recommended outreach sequence

Day 1:

```text
Send observation-led email or LinkedIn DM.
```

Day 3:

```text
Follow up with one sentence and sample report link.
```

Day 5–7:

```text
Call or send final light follow-up.
```

Stop if they say no, unsubscribe, not relevant, or ask not to be contacted.

---

## 12. Git safety

Before committing lead tool changes:

```bash
git status --short
git diff --stat
```

Only commit files under:

```text
internal-tools/system-current-audit-engine/lead_tools/
```

Do not commit:

```text
internal-tools/system-current-audit-engine/outputs/lead_lists/
.env
real lead CSVs
send logs
```

To keep generated output local:

```bash
echo "internal-tools/system-current-audit-engine/outputs/lead_lists/" >> .git/info/exclude
```

If `.env.example` is ignored by `.env*`, force-add only the example file:

```bash
git add -f internal-tools/system-current-audit-engine/lead_tools/.env.example
```

---

## 13. Troubleshooting

### Missing Google API key

Error likely means `GOOGLE_PLACES_API_KEY` is missing from `.env`.

Fix:

```bash
cp lead_tools/.env.example .env
# edit .env and add GOOGLE_PLACES_API_KEY
```

### `python` cannot find pandas

Use the repo venv:

```bash
venv/bin/python lead_tools/run_lead_pipeline.py ...
```

or activate venv:

```bash
source venv/bin/activate
```

### Generated CSVs show in git status

Add local exclude:

```bash
echo "internal-tools/system-current-audit-engine/outputs/lead_lists/" >> .git/info/exclude
```

### Too many weak leads

Use narrower searches:

```text
commercial plumber Vancouver BC
emergency HVAC Burnaby BC
cosmetic dentist Richmond BC
roof repair Surrey BC
physiotherapy clinic Vancouver BC
```

### Too few websites

Try adjacent industries/cities and manually enrich missing websites from the business name.

---

## 14. First-week operating target

For System Current's launch sprint:

```text
Daily raw leads generated:        100
Scored leads reviewed:            30–50
High-priority leads selected:     10–20
Manual outreach messages sent:    10–30
Phone follow-ups:                 5–10
Paid diagnostics target:          1 per day
```

The main KPI is not how many rows the tool generates. The main KPI is:

```text
How many high-quality, manually reviewed outreach messages were sent today?
```

---

## 15. Safe default recommendation

Until the business has reply data, use this system as:

```text
lead intelligence + outreach drafting
```

not as:

```text
automated mass email sending
```

Manual review is part of the system.
