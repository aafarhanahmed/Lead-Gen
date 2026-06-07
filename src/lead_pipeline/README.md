# System Current Lead Tools

Internal CLI tools for building lead lists, preparing diagnostics, and drafting compliant outbound review queues.

These tools reuse the existing audit engine for website scanning, but they do not change the paid fulfillment flow, reports, templates, Streamlit app, checkout, Stripe, or public website.

## What They Do

- Source raw business leads with the official Google Places API Text Search.
- Clean, normalize, and dedupe lead CSVs.
- Lightly inspect public business websites for listed contact emails.
- Run existing System Current audit scans against lead websites.
- Score leads for internal sales prioritization.
- Generate manual-review email, LinkedIn, and phone outreach drafts.
- Optionally send tiny approved email batches through SendGrid.

Generated outputs are saved under:

```bash
outputs/lead_lists/
```

## What They Do Not Do

- No Google Maps scraping.
- No LinkedIn scraping.
- No browser automation for private pages.
- No login, paywall, admin, checkout, or form bypassing.
- No automated email sending by default.
- No CRM or database.
- No spam workflow.

Email sending is optional and only sends rows manually marked `approved_to_send`.

## Setup

Run from:

```bash
cd internal-tools/system-current-audit-engine
source venv/bin/activate
```

Copy the example environment file if useful:

```bash
cp lead_tools/.env.example lead_tools/.env
```

If generated CSVs create local git noise, add this to local exclude instead of editing `.gitignore`:

```bash
echo "internal-tools/system-current-audit-engine/outputs/lead_lists/" >> .git/info/exclude
```

## Environment Variables

- `GOOGLE_PLACES_API_KEY`: required only for `places_lead_builder.py` and the full pipeline.
- `SENDGRID_API_KEY`: required only for real sending with `send_outreach.py --send`.
- `OUTREACH_FROM_EMAIL`: optional sender address; falls back to contact email where possible.
- `OUTREACH_FROM_NAME`: defaults to `Farhan`.
- `SYSTEM_CURRENT_WEBSITE_URL`: defaults to `https://systemcurrent.com`.
- `SYSTEM_CURRENT_SAMPLE_REPORT_URL`: defaults to `https://systemcurrent.com/proof`.
- `SYSTEM_CURRENT_CONTACT_EMAIL`: defaults to `hello@systemcurrent.com`.

## Recommended Workflow

1. Build raw lead list from Places API.
2. Clean and dedupe.
3. Extract public contact emails.
4. Scan websites with the existing audit engine.
5. Generate outreach queue.
6. Manually review top High-priority leads.
7. Manually send or mark selected rows `approved_to_send`.
8. Use the optional sender only in tiny approved batches.

## Commands

Build one raw list:

```bash
python lead_tools/places_lead_builder.py \
  --industry "plumber" \
  --city "Vancouver BC" \
  --output outputs/lead_lists/raw_plumbers_vancouver.csv \
  --max-results 40
```

Build from `lead_tools/queries.csv`:

```bash
python lead_tools/places_lead_builder.py \
  --queries-file lead_tools/queries.csv \
  --output outputs/lead_lists/raw_batch_001.csv \
  --max-results-per-query 25
```

Clean and dedupe:

```bash
python lead_tools/clean_leads.py \
  --input outputs/lead_lists/raw_batch_001.csv \
  --output outputs/lead_lists/clean_batch_001.csv
```

Extract public contact emails:

```bash
python lead_tools/contact_extractor.py \
  --input outputs/lead_lists/clean_batch_001.csv \
  --output outputs/lead_lists/enriched_batch_001.csv \
  --limit 50 \
  --sleep-seconds 1.0
```

Scan and score:

```bash
python lead_tools/bulk_lead_scanner.py \
  --input lead_tools/sample_input.csv \
  --output outputs/lead_lists/scored_leads.csv \
  --limit 2
```

Generate outreach queue:

```bash
python lead_tools/outreach_writer.py \
  --input outputs/lead_lists/scored_batch_001.csv \
  --output outputs/lead_lists/outreach_queue_batch_001.csv \
  --limit 50
```

Full pipeline, excluding email sending:

```bash
python lead_tools/run_lead_pipeline.py \
  --queries-file lead_tools/queries.csv \
  --batch-name batch_001 \
  --max-results-per-query 20 \
  --scan-limit 100 \
  --sleep-seconds 1.5
```

## Output Files

The orchestrator writes:

- `outputs/lead_lists/batch_001_raw.csv`
- `outputs/lead_lists/batch_001_clean.csv`
- `outputs/lead_lists/batch_001_enriched.csv`
- `outputs/lead_lists/batch_001_scored.csv`
- `outputs/lead_lists/batch_001_outreach_queue.csv`

Compliance review fields are preserved through the workflow:

- `email_source_url`
- `consent_basis`
- `relevance_reason`
- `do_not_contact_found`
- `unsubscribe_status`
- `last_contacted_at`
- `outreach_status`

## Manual Review

Before outreach, review:

- Business relevance and fit.
- The observation for accuracy.
- `email_source_url` and `consent_basis`.
- `do_not_contact_found`.
- `unsubscribe_status` and prior contact history.
- Whether the lead should be skipped, manually contacted, or marked `approved_to_send`.

Outreach drafts are preparation material, not automatic approval.

## Optional Sender

Dry run is the default:

```bash
python lead_tools/send_outreach.py \
  --input outputs/lead_lists/outreach_queue_batch_001.csv \
  --log outputs/lead_lists/outreach_send_log.csv \
  --max-send 5
```

Real sending requires `--send`:

```bash
python lead_tools/send_outreach.py \
  --input outputs/lead_lists/outreach_queue_batch_001.csv \
  --log outputs/lead_lists/outreach_send_log.csv \
  --max-send 5 \
  --send
```

Real sending requires all of the following:

- `SENDGRID_API_KEY` is set.
- Row `outreach_status` is exactly `approved_to_send`.
- `consent_basis` is not blank.
- `do_not_contact_found` is not true.
- `email` is not blank.
- `subject` and `email_body` are not blank.

The sender does not add tracking pixels, attachments, hidden unsubscribe handling, or source CSV overwrites. It writes a separate send log only.

## Troubleshooting

- Missing `GOOGLE_PLACES_API_KEY`: Places sourcing exits with a clear error; cleaning, extracting, scanning, writing, and sender dry runs still work.
- Missing `SENDGRID_API_KEY`: sender dry run still works; real sending fails clearly.
- One broken website should not stop a batch. The row is preserved with an error/note where possible.
- Keep generated CSVs out of commits.
