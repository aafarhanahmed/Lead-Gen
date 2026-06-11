from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .config import DEFAULT_MAX_RESULTS_PER_QUERY, DEFAULT_OUTPUT_DIR, DEFAULT_SLEEP_SECONDS


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "raw": output_dir / f"{args.batch_name}_raw.csv",
        "clean": output_dir / f"{args.batch_name}_clean.csv",
        "no_website": output_dir / f"{args.batch_name}_no_website.csv",
        "has_website": output_dir / f"{args.batch_name}_has_website.csv",
        "skipped": output_dir / f"{args.batch_name}_skipped.csv",
        "website_quality": output_dir / f"{args.batch_name}_website_quality.csv",
        "matched": output_dir / f"{args.batch_name}_service_matched.csv",
        "outreach": output_dir / f"{args.batch_name}_outreach_queue.csv",
    }

    run(
        "Places lead builder",
        [
            sys.executable,
            "-m",
            "leadgen.places_lead_builder",
            "--queries-file",
            args.queries_file,
            "--output",
            str(paths["raw"]),
            "--max-results-per-query",
            str(args.max_results_per_query),
            "--mode",
            "enriched",
            "--sleep-seconds",
            str(args.sleep_seconds),
        ] + (["--force-refresh"] if args.force_refresh else []),
    )

    run(
        "Lead cleaner",
        [sys.executable, "-m", "leadgen.clean_leads", "--input", str(paths["raw"]), "--output", str(paths["clean"])],
    )

    split_command = [
        sys.executable,
        "-m",
        "leadgen.no_website_filter",
        "--input",
        str(paths["clean"]),
        "--no-website-output",
        str(paths["no_website"]),
        "--has-website-output",
        str(paths["has_website"]),
        "--skipped-output",
        str(paths["skipped"]),
        "--min-reviews",
        str(args.min_reviews),
        "--min-rating",
        str(args.min_rating),
    ]
    if args.require_phone:
        split_command.append("--require-phone")
    run("No-website splitter", split_command)

    if args.mode == "no-website-first":
        matcher_command = [
            sys.executable,
            "-m",
            "leadgen.service_matcher",
            "--input",
            str(paths["no_website"]),
            "--output",
            str(paths["matched"]),
        ]
    else:
        run(
            "Website quality reviewer",
            [
                sys.executable,
                "-m",
                "leadgen.website_quality",
                "--input",
                str(paths["has_website"]),
                "--output",
                str(paths["website_quality"]),
                "--limit",
                str(args.website_scan_limit),
                "--sleep-seconds",
                str(args.sleep_seconds),
            ],
        )
        matcher_command = [
            sys.executable,
            "-m",
            "leadgen.service_matcher",
            "--input",
            str(paths["website_quality"] if args.mode == "website-quality" else paths["no_website"]),
            "--output",
            str(paths["matched"]),
        ]
        if args.mode == "all":
            matcher_command.extend(["--append-input", str(paths["website_quality"])])
    run("Service matcher", matcher_command)

    run(
        "Outreach writer",
        [
            sys.executable,
            "-m",
            "leadgen.outreach_writer",
            "--input",
            str(paths["matched"]),
            "--output",
            str(paths["outreach"]),
        ],
    )

    print("Pipeline complete.")
    for label, path in paths.items():
        if path.exists():
            print(f"{label}: {path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the standalone local business lead pipeline.")
    parser.add_argument("--queries-file", required=True)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mode", choices=["no-website-first", "website-quality", "all"], default="no-website-first")
    parser.add_argument("--max-results-per-query", type=int, default=DEFAULT_MAX_RESULTS_PER_QUERY)
    parser.add_argument("--website-scan-limit", type=int, default=50)
    parser.add_argument("--min-reviews", type=int, default=0)
    parser.add_argument("--min-rating", type=float, default=0.0)
    parser.add_argument("--require-phone", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    return parser.parse_args()


def run(name: str, command: list[str]) -> None:
    print(f"\nRunning: {name}")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Pipeline stopped at '{name}' with exit code {result.returncode}.")


if __name__ == "__main__":
    raise SystemExit(main())
