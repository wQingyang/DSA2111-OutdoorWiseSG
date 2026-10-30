# Local macOS collector supervision

Use this optional per-user **launchd LaunchAgent** to run the existing
`outdoorwise.cli watch` independently of Terminal. No daemon, database or third-party
supervisor is added. It uses the existing checkout, virtual environment, source
intervals, CSV writer lock, worker lifetime lease and revision history.

Nothing is installed or activated by tests or by rendering the configuration.
The commands below are explicit actions for the operator when ready. Use one
collection mode at a time; stop any foreground collector first. Ordinary API
recommendations consume snapshots; do not also run manual `collect`, explicit live
environment refresh or another scheduled collector against the same runtime.
The lifetime lease protects `watch` instances; manual one-shot collection does not
acquire that lease, although CSV writes remain serialized by the repository lock.

## Prepare and install when ready

From the repository root, first complete the normal `.venv` setup. The launchd
wrapper reads the trusted local `.env` using the same shell convention as the root
README. Keep secrets only in that ignored local file; do not place keys in the plist.
Do not enable shell tracing. Use shell-compatible assignments. `.env` can set
`OUTDOORWISE_DATA_ROOT`, `OUTDOORWISE_ENV_CONFIG`, `DATA_GOV_API_KEY` and optional
`OUTDOORWISE_COLLECTOR_TICK_SECONDS` (default 30). A custom environment file may be
selected using `OUTDOORWISE_ENV_FILE` in the launchd environment; interactive shell
variables are not automatically inherited by launchd. The default data root is
this checkout's `data/`, which must match the API's data root.

```bash
# Rendering only: does not start a collector or contact a provider.
.venv/bin/python scripts/render_macos_collector.py --output /tmp/outdoorwise-collector.plist
plutil -lint /tmp/outdoorwise-collector.plist

# Explicit installation; the job is also eligible to load at subsequent user login.
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/OutdoorWiseSG"
cp /tmp/outdoorwise-collector.plist "$HOME/Library/LaunchAgents/sg.outdoorwise.collector.plist"
chmod 600 "$HOME/Library/LaunchAgents/sg.outdoorwise.collector.plist"
```

The generated configuration uses absolute paths (including paths containing spaces)
and invokes `/bin/zsh scripts/run_macos_collector.zsh`, which `exec`s `.venv/bin/python`.
The worker stays in the foreground as launchd's child. `KeepAlive=true` requests
relaunch after exit, with a 30-second restart throttle, and `ExitTimeOut=180` gives
graceful shutdown time. `RunAtLoad=true` starts it when loaded. The source polling
intervals still come from TOML; neither launchd nor the worker tick changes them.
Re-render after moving the checkout. Keep the old job stopped while replacing its plist.

## Start, stop, restart, status and logs

Run as the logged-in desktop user, without `sudo`:

```bash
# Start (enable also reverses an earlier explicit stop).
launchctl enable "gui/$(id -u)/sg.outdoorwise.collector"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/sg.outdoorwise.collector.plist"

# Stop and keep disabled across login until explicitly enabled again.
launchctl disable "gui/$(id -u)/sg.outdoorwise.collector"
launchctl bootout "gui/$(id -u)/sg.outdoorwise.collector"

# Clean restart (wait for shutdown after bootout, then re-enable/bootstrap).
launchctl disable "gui/$(id -u)/sg.outdoorwise.collector"
launchctl bootout "gui/$(id -u)/sg.outdoorwise.collector"
# Confirm process exit and shutdown event before the following two commands.
launchctl enable "gui/$(id -u)/sg.outdoorwise.collector"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/sg.outdoorwise.collector.plist"
# Do not use kill/launchctl stop as the ordinary stop command: KeepAlive relaunches it.

# Supervisor status: PID, state and last exit status when available.
launchctl print "gui/$(id -u)/sg.outdoorwise.collector"

# Repository diagnostics, using the same .env/data-root setup as the API.
set -a
source .env
set +a
OUTDOORWISE_DATA_MODE=live .venv/bin/python -m outdoorwise.cli status

# View logs (Ctrl-C stops tail, not the collector).
tail -n 40 -f "$HOME/Library/Logs/OutdoorWiseSG/collector.stdout.log" "$HOME/Library/Logs/OutdoorWiseSG/collector.stderr.log"
```

`bootstrap` on an already loaded job reports an error; inspect `launchctl print`
instead of starting another collector. After `bootout`, confirm the final shutdown
event and process exit before starting again. An already unloaded job can also make
`bootout` report an error; distinguish that from a permission error. To uninstall,
stop first, then remove only this agent's plist manually; retain environmental data.

`cli status` is the existing operational command and initializes the repository,
including pending-journal recovery when needed; it is not a forensic read-only
audit command. Do not use it against evidence copies that must remain untouched.
For forensic inspection, read saved JSON/CSV files directly, as the analysis does.

Launchd opens append logs in the user Library directory; no logs or generated
machine-specific plist are committed. Stop the job before manually archiving/rotating
its log files, then restart so new descriptors open. Monitor log and CSV disk usage.
If macOS privacy controls deny access to a checkout in Documents, inspect stderr and
explicitly resolve that access or use a permitted checkout location; the script
does not change privacy or sleep settings.

## Diagnostics and their precise meanings

- `collection_worker.json`: PID, process `started_at`, heartbeat `updated_at`,
  startup/heartbeat/failure/shutdown event, completed cycles, cycle start/end and
  SIGINT/SIGTERM/SIGHUP stop reason when received. SIGKILL/power loss cannot emit a
  shutdown event; an old `state=running` is not proof of a live process.
- Worker `source_diagnostics`: source-run start/end (not exact HTTP timing), batch `last_successful_fetch_at`
  for this process, logged successful-run finish, current-process consecutive
  failures and bounded error category. Source entries update after a completed
  cycle; the persisted heartbeat is not per-request liveness.
- `last_report.sources[].fetched_at`: collector batch fetch time, including successful
  unchanged retrievals. This is after HTTP decoding, not request latency. Failure
  entries have null fetch time. JSON telemetry is additive; CSV schema is unchanged.
- `cli status` source fields reconstruct consecutive failures and latest successful
  run finish across restarts from ingestion logs. `last_retained_fetch_at` is the
  maximum persisted observation fetch, **not a complete history of every successful
  response**. `last_error_category` is bounded (HTTP code, timeout, transport,
  parser/schema or unclassified), with no provider payload or secret copied into it.
- Ingestion-run `finished_at` is assigned before persistence; it is not the exact
  CSV commit time. `last_cycle_finished_at` occurs after refresh/persistence and view
  updates complete, and is a cycle-level completion marker.

Worker source counters reset at process restart, explicitly named
`consecutive_failures_this_process`; repository diagnostics reconstruct persisted
counters. A successful HTTP/parse/ingestion cycle does not establish that observation
timestamps are recent. Source failures stay logged and other sources continue;
unexpected disk/schema failures stop the worker and surface an error for supervision.
The existing Kubernetes heartbeat probe tolerates up to 30 minutes between completed
cycles because retries across eight sources can be lengthy. It is not a freshness SLA.

## Failure modes and validation limits

Closing Terminal does not own this LaunchAgent. A foreground Terminal collector can
receive SIGHUP or be terminated, depending on terminal settings; no historical
Terminal closure is inferred from a gap. New CLI workers handle SIGHUP gracefully,
as well as SIGINT/SIGTERM, while launchd keeps the configured service running until
explicitly unloaded/disabled.

A **LaunchAgent runs only while its user is logged in**. Logout stops it; login
can reload an installed/enabled job. Reboot does not collect until the next login.
Sleep suspends ordinary local execution; shutdown/power loss prevents it. Wake can
resume due checks or supervision, but cannot recover measurements the provider no
longer returns. Network loss produces attempted failures if the process is running;
it cannot be repaired by a restart policy. Do not equate these conditions with one
another. Uninterrupted 24/7 collection requires an always-on host with connectivity.
No sleep settings are changed by this solution.

Compose already has `restart: unless-stopped`; Kubernetes already supervises a
single collector with a shared PVC and heartbeat probes. They remain unchanged.
Docker Desktop on this Mac still depends on host uptime; its named runtime volume
does not automatically include the host's collected CSVs. The LaunchAgent is chosen
here to preserve the existing host data path without migration.

Automated tests render/parse the plist, validate the real wrapper in temporary data
storage, simulate a failed source followed by recovery, kill and restart a worker,
check lease release/duplicate rejection and verify unchanged observation/history
hashes. **No LaunchAgent is loaded during tests.** Native launchd crash relaunch,
sleep/wake, logout/login and reboot recovery have not been exercised on this machine.
The expected supervisor behavior follows Apple's documentation, not a claimed live
acceptance test.

Official references: [Apple launchd guide](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html),
[Apple Terminal service management](https://support.apple.com/en-asia/guide/terminal/apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac).
