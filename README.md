# Lead-Gen

Python-supported public business research workflow for creating structured local business prospect lists.

## Use Case

Input:
- niche/business category
- city/location
- optional source or filtering rules

Output:
- clean CSV/Google Sheet-ready business prospect list

## Typical Fields

- Business name
- Website
- Phone number
- Address/location
- Business category
- Source URL
- Contact page/contact path where publicly available
- Public email where available
- Website/contact quality notes
- Deduplication status
- Lead score / priority notes

## Positioning

This project supports public business research workflows.

It is not designed for:
- LinkedIn scraping
- Sales Navigator scraping
- restricted-platform scraping
- private personal-data harvesting
- cold calling
- appointment setting
- PPC campaign management

## Setup

Run:

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

## Notes

Raw lead exports, API keys, credentials, and client data should not be committed to this repo.
