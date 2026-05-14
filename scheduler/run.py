"""Periodic ingest runner. Long-lived loop or one-shot via --once."""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.ingest import (
    ingest_jira, ingest_pdfs, ingest_playwright, ingest_selenium, ingest_testcases,
)
from backend.lib import settings

RUNNERS: dict[str, Callable[..., dict]] = {
    "selenium": ingest_selenium.run,
    "playwright": ingest_playwright.run,
    "testcases": ingest_testcases.run,
    "pdfs": ingest_pdfs.run,
    "jira": ingest_jira.run,
}

LOG_PATH = settings.CHAPTER_ROOT / "data" / "_scheduler.log"
REPORT_PATH = settings.CHAPTER_ROOT / "data" / "_ingest_report.json"

log = logging.getLogger("scheduler")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    rotating = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    rotating.setFormatter(fmt)
    root.addHandler(rotating)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def _acquire_lock(lock_file: Path) -> bool:
    # Lock rationale: Qdrant file-store is single-process. Two overlapping
    # ingest cycles would block on the same file lock and stall the scheduler.
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "started": _now()}))
    return True


def _release_lock(lock_file: Path) -> None:
    try:
        lock_file.unlink()
    except FileNotFoundError:
        pass


def _append_report(entry: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if REPORT_PATH.exists():
        try:
            existing = json.loads(REPORT_PATH.read_text() or "null")
            if isinstance(existing, list):
                history = existing
            elif isinstance(existing, dict):
                history = [existing]
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    REPORT_PATH.write_text(json.dumps(history[-50:], indent=2))


def run_cycle(targets: list[str], recreate: bool, lock_file: Path) -> dict:
    if not _acquire_lock(lock_file):
        log.warning("lock file present at %s, skipping cycle", lock_file)
        return {"timestamp": _now(), "skipped": True, "reason": "locked"}

    started = _now()
    results: list[dict] = []
    try:
        for name in targets:
            runner = RUNNERS.get(name)
            if runner is None:
                log.error("unknown ingest target: %s", name)
                results.append({"collection": name, "error": "unknown target"})
                continue
            log.info("ingest start: %s (recreate=%s)", name, recreate)
            try:
                res = runner(recreate=recreate)
                log.info("ingest done: %s -> %s", name, json.dumps(res, default=str))
                results.append(res if isinstance(res, dict) else {"collection": name, "result": res})
            except Exception as e:
                log.exception("ingest failed: %s", name)
                results.append({"collection": name, "error": str(e)})
    finally:
        _release_lock(lock_file)

    entry = {
        "timestamp": started,
        "finished": _now(),
        "targets": targets,
        "recreate": recreate,
        "results": results,
    }
    _append_report(entry)
    return entry


def _install_signal_handlers(scheduler: BlockingScheduler) -> None:
    def _stop(signum, _frame):
        log.info("signal %s received, shutting down", signum)
        scheduler.shutdown(wait=False)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Periodic ingest runner for QA Copilot.")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit (suitable for cron / launchd / systemd timer).")
    args = parser.parse_args(argv)

    _configure_logging()
    targets = settings.INGEST_TARGETS_LIST
    recreate = settings.INGEST_RECREATE
    interval = settings.INGEST_INTERVAL_MINUTES
    lock_file = settings.INGEST_LOCK_FILE

    log.info("config: targets=%s interval=%smin recreate=%s startup=%s lock=%s",
             targets, interval, recreate, settings.INGEST_AT_STARTUP, lock_file)

    if args.once:
        entry = run_cycle(targets, recreate, lock_file)
        print(json.dumps(entry, indent=2))
        return 0

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_cycle,
        trigger=IntervalTrigger(minutes=interval),
        kwargs={"targets": targets, "recreate": recreate, "lock_file": lock_file},
        id="ingest_cycle", max_instances=1, coalesce=True, replace_existing=True,
    )
    _install_signal_handlers(scheduler)

    if settings.INGEST_AT_STARTUP:
        log.info("running startup cycle before interval loop")
        run_cycle(targets, recreate, lock_file)

    log.info("entering blocking scheduler loop (every %s min)", interval)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
