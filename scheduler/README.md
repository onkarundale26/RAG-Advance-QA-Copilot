# Scheduler

Periodic runner for the five QA Copilot ingest pipelines (Selenium, Playwright,
test cases CSV, PDFs, JIRA markdown). Wraps the existing
`backend.ingest.ingest_*.run(recreate=...)` callables in an APScheduler
`BlockingScheduler` so a single Python process re-indexes Qdrant on a fixed
interval without any extra infrastructure.

## What it does

- Reads scheduling config from `Chapter_09_Project_QACopilot/.env` via
  `backend.lib.settings`.
- On each tick: acquires a lock file, runs each selected pipeline, captures
  per-pipeline result (or exception), appends an entry to
  `data/_ingest_report.json`, releases the lock.
- Logs to stdout and to `data/_scheduler.log` (rotating, 1 MB, 3 backups).
- Handles SIGINT / SIGTERM and shuts the scheduler down without waiting for
  in-flight jobs.

## Env vars

| Variable | Default | Description |
|---|---|---|
| `INGEST_INTERVAL_MINUTES` | `60` | Minutes between cycles in long-lived mode. |
| `INGEST_AT_STARTUP` | `true` | If true, run one cycle immediately at startup, then enter the interval loop. |
| `INGEST_TARGETS` | `selenium,playwright,testcases,pdfs,jira` | Comma-separated subset of pipelines to run each cycle. |
| `INGEST_RECREATE` | `false` | If true, drop and rebuild every selected collection on each cycle (expensive). |
| `INGEST_LOCK_FILE` | `<CHAPTER_ROOT>/data/.ingest.lock` | Path to the lock file used to skip overlapping cycles. |

## Run examples

Long-lived loop (default cadence from `.env`):

```bash
python -m scheduler.run
```

One cycle then exit (useful for cron / launchd / systemd timers):

```bash
python -m scheduler.run --once
```

Override targets for a single run:

```bash
INGEST_TARGETS=testcases,jira python -m scheduler.run --once
```

## macOS launchd snippet

Save as `~/Library/LaunchAgents/com.qacopilot.ingest.plist` and load with
`launchctl load ~/Library/LaunchAgents/com.qacopilot.ingest.plist`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.qacopilot.ingest</string>
  <key>WorkingDirectory</key>
  <string>/Users/YOU/path/to/Chapter_09_Project_QACopilot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/path/to/Chapter_09_Project_QACopilot/.venv/bin/python</string>
    <string>-m</string>
    <string>scheduler.run</string>
    <string>--once</string>
  </array>
  <key>StartInterval</key><integer>3600</integer>
  <key>StandardOutPath</key>
  <string>/Users/YOU/path/to/Chapter_09_Project_QACopilot/data/_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/YOU/path/to/Chapter_09_Project_QACopilot/data/_launchd.err.log</string>
</dict>
</plist>
```

## Linux systemd timer snippet

`/etc/systemd/system/qacopilot-ingest.service`:

```ini
[Unit]
Description=QA Copilot ingest one-shot
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/qacopilot/Chapter_09_Project_QACopilot
ExecStart=/opt/qacopilot/Chapter_09_Project_QACopilot/.venv/bin/python -m scheduler.run --once
User=qacopilot
```

`/etc/systemd/system/qacopilot-ingest.timer`:

```ini
[Unit]
Description=Run QA Copilot ingest every hour

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h
Unit=qacopilot-ingest.service

[Install]
WantedBy=timers.target
```

Enable with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qacopilot-ingest.timer
```

## Integration with the FastAPI app

Run the scheduler as a separate process from `uvicorn backend.main:app`. Do
**not** start it from inside FastAPI (e.g. via `@app.on_event("startup")`).

Reason: the default Qdrant configuration in this chapter is the embedded
file-store at `QDRANT_PATH`. The file-store is single-process; an ingest
running inside the API process would block requests while it holds the lock,
and an ingest running in a sibling thread would race the request handlers on
the same file lock. The scheduler uses `INGEST_LOCK_FILE` to avoid overlapping
its own cycles, but it cannot coordinate with the API's in-process Qdrant
client.

If you need ingest to run while the API serves traffic, switch both processes
to HTTP mode by setting `QDRANT_URL` to a running Qdrant server. Then both the
API and the scheduler talk to that server and the file-store contention goes
away.
