from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "leadgen.run_pipeline",
        "--queries-file",
        "data/queries/calgary_home_services.csv",
        "--batch-name",
        "calgary_home_services_001",
        "--max-results-per-query",
        "20",
        "--mode",
        "no-website-first",
        "--min-reviews",
        "10",
        "--min-rating",
        "4.0",
        "--require-phone",
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
