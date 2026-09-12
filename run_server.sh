#!/usr/bin/env bash
# Start (or restart) the FlexGet daemon.
#
# Usage:
#   ./run_server.sh           — start the daemon if it is not already running
#   ./run_server.sh restart   — stop the running daemon (if any), then restart it (to pick up any code changes)
#   ./run_server.sh stop      — stop the running daemon (if any)
#
# Optional environment variables:
#   FLEXGET_CONFIG   Path to the FlexGet config file (default: config.yml)

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# --- Load .env if present (does not overwrite variables already set in the environment) ---
if [[ -f .env ]]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        [[ -v "$key" ]] && continue
        export "$key=$value"
    done < .env
fi

# --- Validate arguments ---
MODE="${1:-}"
if [[ -n "$MODE" && "$MODE" != "restart" && "$MODE" != "stop" ]]; then
    echo "Usage: $0 [restart|stop]" >&2
    exit 1
fi

if [[ -z "${FLEXGET_CONFIG:-}" ]]; then
    if [[ ! -f .venv/config.yml ]]; then
        echo "==> No config found — creating default .venv/config.yml"
        cat > .venv/config.yml <<'EOF'
tasks:
  test-task:
    rss: http://mysite.com/myfeed.rss
    series:
      - My Favorite Show
      - Another Good Show:
          quality: 720p
    download: /home/me/watchdir/
web_server: true
EOF
    fi
    FLEXGET_CONFIG=./.venv/config.yml
fi
FLEXGET=(uv run flexget -c "${FLEXGET_CONFIG}")

# --- Helpers ---
is_running() {
    local output
    output=$("${FLEXGET[@]}" daemon status 2>/dev/null) || true
    echo "$output" | grep -q "Daemon running"
}

start_daemon() {
    echo "==> Starting FlexGet daemon..."
    "${FLEXGET[@]}" daemon start -d
    echo "==> FlexGet daemon started."
}

stop_daemon() {
    echo "==> Stopping FlexGet daemon..."
    "${FLEXGET[@]}" daemon stop
    local attempts=0
    while is_running; do
        if (( ++attempts >= 30 )); then
            echo "Error: daemon did not stop within 30 seconds." >&2
            exit 1
        fi
        sleep 1
    done
    echo "==> FlexGet daemon stopped."
}

# --- Main ---
if [[ "$MODE" == "stop" ]]; then
    if is_running; then
        stop_daemon
    else
        echo "==> No daemon currently running."
    fi
elif [[ "$MODE" == "restart" ]]; then
    if is_running; then stop_daemon; else echo "==> No daemon currently running."; fi
    start_daemon
else
    if is_running; then
        echo "==> FlexGet daemon is already running."
    else
        start_daemon
    fi
fi
