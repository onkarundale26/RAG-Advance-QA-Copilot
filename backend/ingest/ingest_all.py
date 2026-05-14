"""Run all 5 ingest pipelines. Writes a JSON report next to data/."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from ..lib import settings
from . import ingest_jira, ingest_pdfs, ingest_playwright, ingest_selenium, ingest_testcases


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--recreate", action="store_true",
                   help="Drop and recreate every collection before ingesting.")
    p.add_argument("--only", nargs="*",
                   choices=["selenium", "playwright", "testcases", "pdfs", "jira"],
                   help="Run only the named pipelines (default: all).")
    args = p.parse_args()

    targets = args.only or ["selenium", "playwright", "testcases", "pdfs", "jira"]
    runners = {
        "selenium": ingest_selenium.run,
        "playwright": ingest_playwright.run,
        "testcases": ingest_testcases.run,
        "pdfs": ingest_pdfs.run,
        "jira": ingest_jira.run,
    }
    results = []
    for name in targets:
        print(f"\n=== Ingesting: {name} ===")
        try:
            res = runners[name](recreate=args.recreate)
        except Exception as e:
            res = {"collection": name, "error": str(e)}
            print(f"  ERROR: {e}")
        results.append(res)

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    report_path = settings.CHAPTER_ROOT / "data" / "_ingest_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {report_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
