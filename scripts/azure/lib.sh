#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

SCRIPT_DIR="${DR_SCRIPT_DIR:-$REPO_ROOT/scripts/azure}"

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

if [ -z "${BACKUP_ACCOUNT_KEY:-}" ] && [ -s "$PRIVATE_DIR/key-$BACKUP_ACCOUNT" ]; then
  BACKUP_ACCOUNT_KEY="$(cat "$PRIVATE_DIR/key-$BACKUP_ACCOUNT")"
  export BACKUP_ACCOUNT_KEY
fi

session() { (cd "$REPO_ROOT" && "$DR_PYTHON" -m scripts.dr.session_state "$@"); }

refresh_admin_ip() {
  local ip="${ADMIN_IP:-$(curl -fsS https://api.ipify.org)}"
  [ -n "$ip" ] || die 1 "không lấy được IP hiện tại cho quy tắc admin"
  az network nsg rule update -g "rg-dr-$1" --nsg-name "vm-dr-$1-nsg" -n admin \
    --source-address-prefixes "$ip/32" -o none || die 1 "không cập nhật được quy tắc admin của vm-dr-$1"
}
