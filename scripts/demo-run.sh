#!/bin/sh
# Live ingest demo (~2 minutes): mock feed + the scheduler firing jobs on their own
# `schedule:` lines.
#
#   sh scripts/demo-run.sh
#
# Watch the scheduler's own log, or point an agent at http://127.0.0.1:8421/mcp and
# ask what is landing while it runs.

set -eu

ROOT="$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FEED_HOST="${DEMO_FEED_HOST:-127.0.0.1}"
FEED_PORT="${DEMO_FEED_PORT:-8765}"
QANAT_PORT="${QANAT_HOST_PORT:-8421}"
DURATION="${DEMO_DURATION:-120}"

FEED_PID=""
QANAT_PID=""

cleanup() {
  kill "$QANAT_PID" "$FEED_PID" 2>/dev/null || true
  wait "$QANAT_PID" "$FEED_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if ! command -v uv >/dev/null 2>&1; then
  echo "demo-run: uv is required" >&2
  exit 1
fi

echo "demo-run: starting mock feed on http://${FEED_HOST}:${FEED_PORT}"
python3 "$ROOT/scripts/demo-feed.py" &
FEED_PID=$!

for _ in $(seq 1 30); do
  if curl -sf "http://${FEED_HOST}:${FEED_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done
curl -sf "http://${FEED_HOST}:${FEED_PORT}/health" >/dev/null || {
  echo "demo-run: feed did not start" >&2
  exit 1
}

echo "demo-run: bootstrapping history + first pipeline pass"
cd "$ROOT/examples/scheduled-ingest"
uv run --project "$ROOT" qanat check
uv run --project "$ROOT" qanat run bars_seed
for job in news normalize momentum risk tone portfolio; do
  uv run --project "$ROOT" qanat run "$job"
done

# Every job in this project carries a `schedule:`, so the scheduler fires the whole
# pipeline each minute by itself. Nothing here has to poke it: a loop that triggered
# jobs from outside would be testing the loop rather than the schedule.
echo "demo-run: mcp → http://127.0.0.1:${QANAT_PORT}/mcp"
uv run --project "$ROOT" qanat serve --host 127.0.0.1 --port "$QANAT_PORT" --run-now \
  --log-level info &
QANAT_PID=$!

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${QANAT_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

echo ""
echo "  mcp      http://127.0.0.1:${QANAT_PORT}/mcp"
echo "  Sources and steps fire on their own schedules, about once a minute."
echo "  Running for ~${DURATION}s. Press Ctrl+C to stop the feed and the scheduler."
echo ""

sleep "$DURATION" &
wait $! 2>/dev/null || true
echo "demo-run: ${DURATION}s elapsed, stopping"
