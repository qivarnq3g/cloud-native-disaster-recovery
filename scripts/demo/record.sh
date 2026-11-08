#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export DEMO_DIR="${DEMO_DIR:-$ROOT/demo}"
mkdir -p "$DEMO_DIR"
name="${1:-}"
case "$name" in
  normal|D1|D3|D6) ;;
  *) echo "dùng: record.sh normal|D1|D3|D6" >&2; exit 64 ;;
esac
cd "$ROOT"
rm -f "$DEMO_DIR/$name.status"
asciinema rec --overwrite --quiet --cols 140 --rows 34 -c "bash scripts/demo/scene.sh $name" "$DEMO_DIR/$name.cast"
status="$(cat "$DEMO_DIR/$name.status" 2>/dev/null || echo 1)"
echo "$name: exit $status"
exit "$status"
