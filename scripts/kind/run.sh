#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
SCENARIO="${1:-}"; shift || true
ITERATIONS=""; KEEP=false
while [ $# -gt 0 ]; do
  case "$1" in
    --iterations) ITERATIONS="$2"; shift 2 ;;
    --keep) KEEP=true; shift ;;
    *) log "không hiểu $1"; exit 64 ;;
  esac
done
case "$SCENARIO" in
  D1|D2|D6) PROFILE=primary ;;
  D3) PROFILE=full ;;
  *) log "dùng: run.sh D1|D2|D3|D6 [--iterations N] [--keep]"; exit 64 ;;
esac
PREFIX="${RUN_PREFIX:-local}"

once() {
  local iteration="$1" run_id
  run_id="$PREFIX-$SCENARIO-$iteration-$(date -u +%Y%m%d%H%M%S)"
  export DR_KIND_RUN_ID="$run_id"
  if [ -n "$ITERATIONS" ]; then
    "$ROOT/scripts/kind/down.sh"
    "$ROOT/scripts/kind/up.sh" --profile "$PROFILE" || { diagnose "$run_id"; return 1; }
  fi
  "$PYTHON" -m scripts.kind.scenario "$SCENARIO" --run-id "$run_id" --iteration "$iteration" \
    || { diagnose "$run_id"; return 1; }
}

if [ -z "$ITERATIONS" ]; then
  [ -f "$STATE_DIR/profile" ] || { log "chưa có môi trường, chạy scripts/kind/up.sh trước"; exit 1; }
  if [ "$PROFILE" = full ] && [ "$(cat "$STATE_DIR/profile")" != full ]; then
    log "$SCENARIO cần cụm dự phòng: chạy scripts/kind/up.sh (không có --profile primary)"; exit 1
  fi
  once 1
  exit
fi

failed=0
for i in $(seq 1 "$ITERATIONS"); do
  log "$SCENARIO: lần $i/$ITERATIONS"
  once "$i" || { failed=$((failed + 1)); log "$SCENARIO lần $i không đạt"; }
done
$KEEP || "$ROOT/scripts/kind/down.sh"
log "$SCENARIO: $((ITERATIONS - failed))/$ITERATIONS lần đạt"
[ "$failed" -eq 0 ]
