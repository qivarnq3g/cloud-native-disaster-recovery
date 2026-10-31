#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

SCRIPT_DIR="${DR_SCRIPT_DIR:-$REPO_ROOT/scripts/azure}"
DIGEST_SQL="SELECT md5(coalesce(string_agg(id::text || ':' || encode(image_sha256, 'hex'), ',' ORDER BY id), '')) FROM posts"

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

account_key() {
  local account="$1" file="$PRIVATE_DIR/key-$1" group
  if [ ! -s "$file" ]; then
    case "$account" in
      "$IMAGE_PRIMARY_ACCOUNT") group="$RG_PRIMARY" ;;
      "$IMAGE_STANDBY_ACCOUNT") group="$RG_STANDBY" ;;
      *) group="$RG_BACKUP" ;;
    esac
    az storage account keys list -g "$group" -n "$account" --query "[0].value" -o tsv > "$file"
    chmod 600 "$file"
  fi
  cat "$file"
}

dns_switch() {
  if [ -n "${DR_DNS_SWITCH:-}" ]; then "$DR_DNS_SWITCH" "$@"
  else (cd "$REPO_ROOT" && "$DR_PYTHON" -m scripts.dr.dns_switch "$@"); fi
}

run_step() {
  local run_id="$1" step="$2"; shift 2
  if [ -z "$run_id" ]; then "$@"; return; fi
  [ -f "$DATA_DIR/drills/$run_id/steps.csv" ] || bash "$REPO_ROOT/scripts/azure/step.sh" "$run_id" --new
  bash "$REPO_ROOT/scripts/azure/step.sh" "$run_id" "$step" -- "$@"
}

remove_image_replication() {
  local id
  for id in $(az storage account or-policy list -g "$RG_STANDBY" --account-name "$IMAGE_STANDBY_ACCOUNT" \
      --query "[?destinationAccount=='$IMAGE_STANDBY_ACCOUNT'].policyId" -o tsv); do
    az storage account or-policy delete -g "$RG_STANDBY" --account-name "$IMAGE_STANDBY_ACCOUNT" --policy-id "$id" -o none \
      || die 1 "không gỡ được chính sách chép ảnh $id"
  done
}

switch_to() {
  local cluster="$1" server="$2" ip
  [ -n "$server" ] || die 5 "chưa biết server_name mới của $cluster"
  ip="$(az vm show -d -g "rg-dr-$cluster" -n "vm-dr-$cluster" --query publicIps -o tsv)" || ip=
  [ -n "$ip" ] || die 1 "không lấy được IP của vm-dr-$cluster"
  dns_switch "$ip" --csv "$DATA_DIR/dns-switch.csv" || die 1 "đổi DNS sang $cluster lỗi"
  session set "cluster=$cluster" "server_name=$server" state=running
}
