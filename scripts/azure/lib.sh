#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

die() { local code="$1"; shift; echo "$*" >&2; exit "$code"; }

check_cluster() {
  case "${1:-}" in primary|standby) ;; *) die 64 "cụm phải là primary hoặc standby" ;; esac
}

vm_exists() { az vm show -g "rg-dr-$1" -n "vm-dr-$1" --query name -o tsv >/dev/null 2>&1; }

vm_count() {
  local n=0 c
  for c in primary standby; do
    if vm_exists "$c"; then n=$((n + 1)); fi
  done
  echo "$n"
}

power_state() {
  az vm get-instance-view -g "rg-dr-$1" -n "vm-dr-$1" \
    --query "instanceView.statuses[?starts_with(code,'PowerState/')].code" -o tsv
}

mark() {
  local f="$DATA_DIR/$1"
  [ -f "$f" ] || echo "cluster,mark,time_utc" > "$f"
  echo "$2,$3,$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$f"
}

session() { (cd "$REPO_ROOT" && "$DR_PYTHON" -m scripts.dr.session_state "$@"); }
