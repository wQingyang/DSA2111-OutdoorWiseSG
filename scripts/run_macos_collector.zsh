#!/bin/zsh
# launchd owns the foreground process; exec preserves its signal/exit supervision.
set -eu
task_root="${0:A:h:h}"
cd "$task_root"
# Match the documented trusted local shell .env format, without printing values.
task_env_file="${OUTDOORWISE_ENV_FILE:-$task_root/.env}"
if [[ -f "$task_env_file" ]]; then
    set -a
    source "$task_env_file"
    set +a
fi
export OUTDOORWISE_DATA_MODE="${OUTDOORWISE_DATA_MODE:-live}"
export OUTDOORWISE_DATA_ROOT="${OUTDOORWISE_DATA_ROOT:-$task_root/data}"
exec "$task_root/.venv/bin/python" -m outdoorwise.cli watch \
    --tick-seconds "${OUTDOORWISE_COLLECTOR_TICK_SECONDS:-30}"
