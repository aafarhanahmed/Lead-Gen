"""Run the internal lead pipeline through outreach queue generation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from lead_tools.config import DEFAULT_MAX_RESULTS_PER_QUERY, DEFAULT_SLEEP_SECONDS
except ImportError:
    from config import DEFAULT_MAX_RESULTS_PER_QUERY, DEFAULT_SLEEP_SECONDS


def main() -> int:
    args = parse_args()
    output_dir = Path("outputs/lead_lists")
    paths = {
        "raw": output_dir / f"{args.batch_name}_raw.csv",
        "clean": output_dir / f"{args.batch_name}_clean.csv",
        "enriched": output_dir / f"{args.batch_name}_enriched.csv",
        "scored": output_dir / f"{args.batch_name}_scored.csv",
        "queue": output_dir / f"{args.batch_name}_outreach_queue.csv",
    }

    phases = [
        (
            "Places lead builder",
            [
                sys.executable,
                "lead_tools/places_lead_builder.py",
                "--queries-file",
                args.queries_file,
                "--output",
                str(paths["raw"]),
                "--max-results-per-query",
                str(args.max_results_per_query),
                "--sleep-seconds",
                str(args.sleep_seconds),
            ],
        ),
        (
            "Lead cleaner",
            [sys.executable, "lead_tools/clean_leads.py", "--input", str(paths["raw"]), "--output", str(paths["clean"])],
        ),
        (
            "Contact extractor",
            [
                sys.executable,
                "lead_tools/contact_extractor.py",
                "--input",
                str(paths["clean"]),
                "--output",
                str(paths["enriched"]),
                "--limit",
                str(args.scan_limit),
                "--sleep-seconds",
                str(args.sleep_seconds),
            ],
        ),
        (
            "Bulk lead scanner",
            [
                sys.executable,
                "lead_tools/bulk_lead_scanner.py",
                "--input",
                str(paths["enriched"]),
                "--output",
                str(paths["scored"]),
                "--limit",
                str(args.scan_limit),
                "--sleep-seconds",
                str(args.sleep_seconds),
            ],
        ),
        (
            "Outreach writer",
            [
                sys.executable,
                "lead_tools/outreach_writer.py",
                "--input",
                str(paths["scored"]),
                "--output",
                str(paths["queue"]),
                "--limit",
                str(args.scan_limit),
            ],
        ),
    ]

    for name, command in phases:
        print(f"Running phase: {name}")
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(f"Pipeline stopped. Phase failed: {name} (exit {result.returncode})", file=sys.stderr)
            return result.returncode

    print("Pipeline complete.")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lead sourcing through outreach draft generation.")
    parser.add_argument("--queries-file", required=True)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--max-results-per-query", type=int, default=DEFAULT_MAX_RESULTS_PER_QUERY)
    parser.add_argument("--scan-limit", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
