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

take_full_backup() {
  local name="$1" id
  printf '%s\n' \
    "apiVersion: postgresql.cnpg.io/v1" \
    "kind: Backup" \
    "metadata:" \
    "  name: $name" \
    "spec:" \
    "  cluster:" \
    "    name: db" \
    "  method: plugin" \
    "  pluginConfiguration:" \
    "    name: barman-cloud.cloudnative-pg.io" \
    | kubectl -n dr-api apply -f - >&2 || die 1 "không tạo được bản đầy đủ $name"
  kubectl -n dr-api wait --for=jsonpath='{.status.phase}'=completed "backups.postgresql.cnpg.io/$name" --timeout=1800s >&2 \
    || die 1 "bản đầy đủ $name không hoàn thành, giữ máy"
  id="$(kubectl -n dr-api get "backups.postgresql.cnpg.io/$name" -o jsonpath='{.status.backupId}')" && [ -n "$id" ] \
    || die 1 "bản đầy đủ $name không có backupId, giữ máy"
  echo "$id"
}
