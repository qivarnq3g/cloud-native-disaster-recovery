#!/usr/bin/env bash
# Biến và hàm dùng chung cho các script của bản thu nhỏ trên kind (mục 6.4 thiết kế).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT
# Khóa và trạng thái dùng một lần, ngoài kho; down.sh xóa.
export STATE_DIR="${DR_KIND_STATE:-$HOME/.dr-kind}"
export DATA_DIR="${DR_KIND_DATA:-$ROOT/data/kind}"
export PRIMARY_PORT="${PRIMARY_PORT:-18080}"
export STANDBY_PORT="${STANDBY_PORT:-28080}"
export S3_PORT=18333
export API_IMAGE="${API_IMAGE:-dr-api:kind}"
export SEAWEEDFS_IMAGE=docker.io/chrislusf/seaweedfs:4.48
export RCLONE_IMAGE=docker.io/rclone/rclone:1.75.2
export CERT_MANAGER_VERSION=v1.21.2
export CNPG_CHART_VERSION=0.29.1
export BARMAN_VERSION=v0.15.1
export VELERO_CHART_VERSION=12.2.1
export PYTHON="${PYTHON:-python3}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }

ctx() { echo "kind-$1"; }

k() { local c="$1"; shift; kubectl --context "$(ctx "$c")" "$@"; }

port_of() { if [ "$1" = primary ]; then echo "$PRIMARY_PORT"; else echo "$STANDBY_PORT"; fi; }

cred() { "$PYTHON" -m scripts.kind.store get "$STATE_DIR" "$1" "$2"; }

# Ghi một mốc vào data/kind/up.csv: run_id,cluster,step,started_at,ended_at,duration_s
timed() {
  local cluster="$1" step="$2"; shift 2
  local t0 t1 s0 s1
  t0="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"; s0="$(date +%s.%N)"
  "$@"
  t1="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"; s1="$(date +%s.%N)"
  mkdir -p "$DATA_DIR"
  [ -s "$DATA_DIR/up.csv" ] || echo "run_id,cluster,step,started_at,ended_at,duration_s" > "$DATA_DIR/up.csv"
  echo "${DR_KIND_RUN_ID:-manual},$cluster,$step,$t0,$t1,$(awk "BEGIN{printf \"%.1f\", $s1-$s0}")" >> "$DATA_DIR/up.csv"
}

# Gói mọi image cần nạp vào cụm (chỉ nền tảng của máy) thành một tệp, giữ trong thư mục cache để các
# lần dựng sau dùng lại. Tên tệp đổi khi danh sách image hay image API đổi. Gói xong thì xóa bản trong
# Docker của máy: máy GitHub chỉ còn khoảng 14 GB trống, giữ cả hai bản thì đầy ổ.
image_archive() {
  local images key dir img
  images="$(grep -v '^#' "$ROOT/infra/kind/images.txt")"
  key="$( { echo "$images $API_IMAGE"; docker image inspect -f '{{.Id}}' "$API_IMAGE"; } | sha256sum | cut -c1-12)"
  dir="${XDG_CACHE_HOME:-$HOME/.cache}/dr-kind"
  if [ ! -s "$dir/images-$key.tar" ]; then
    mkdir -p "$dir"; rm -f "$dir"/images-*.tar
    for img in $images; do docker image inspect "$img" >/dev/null 2>&1 || docker pull -q "$img" >/dev/null; done
    # shellcheck disable=SC2086
    docker save --platform "linux/$(docker version -f '{{.Server.Arch}}')" -o "$dir/images-$key.tar.tmp" $images "$API_IMAGE"
    mv "$dir/images-$key.tar.tmp" "$dir/images-$key.tar"
    # shellcheck disable=SC2086
    docker rmi $images >/dev/null 2>&1 || true
  fi
  echo "$dir/images-$key.tar"
}

new_server_name() { echo "$1-$(date -u +%Y%m%d%H%M%S)"; }

# Áp một mẫu cấu hình, thay các __TÊN__ theo cặp TÊN=giá_trị.
apply_tpl() {
  local cluster="$1" tpl="$2"; shift 2
  local args=()
  for pair in "$@"; do args+=(-e "s|__${pair%%=*}__|${pair#*=}|g"); done
  sed "${args[@]}" "$tpl" | k "$cluster" apply -f -
}

# Secret và ConfigMap riêng của từng cụm trong namespace dr-api (mục 2.5 thiết kế web).
# $2: bucket ảnh, $3: true nếu API chạy chế độ chỉ đọc.
site_config() {
  local cluster="$1" bucket="$2" read_only="$3" identity="api-$1"
  k "$cluster" create namespace dr-api --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
  k "$cluster" -n dr-api create secret generic backup-store \
    --from-literal=ACCESS_KEY_ID="$(cred cnpg access)" --from-literal=ACCESS_SECRET_KEY="$(cred cnpg secret)" \
    --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
  k "$cluster" -n dr-api create secret generic db-app-user --type=kubernetes.io/basic-auth \
    --from-literal=username=dr --from-literal=password="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["db_password"])' "$STATE_DIR/credentials.json")" \
    --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
  k "$cluster" -n dr-api create secret generic api-secret-code --from-file=SECRET_CODE="$STATE_DIR/secret-code" \
    --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
  k "$cluster" -n dr-api create secret generic image-store \
    --from-literal=AWS_ACCESS_KEY_ID="$(cred "$identity" access)" --from-literal=AWS_SECRET_ACCESS_KEY="$(cred "$identity" secret)" \
    --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
  k "$cluster" -n dr-api create configmap api-site --from-literal=CLUSTER="$cluster" --from-literal=REGION=kind \
    --from-literal=IMAGE_STORE_CONTAINER="$bucket" --from-literal=IMAGE_STORE_READ_ONLY="$read_only" \
    --dry-run=client -o yaml | k "$cluster" apply -f - >/dev/null
}

wait_db() { k "$1" -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout="${2:-900s}"; }

deploy_api() {
  k "$1" apply -k "$ROOT/infra/k8s/overlays/kind" >/dev/null
  k "$1" -n dr-api rollout status deploy/api --timeout=300s
}

# Chờ /healthz của cụm trả 200 qua cổng trên máy.
wait_healthy() {
  local port; port="$(port_of "$1")"
  for _ in $(seq 1 "${2:-300}"); do
    curl -fsS -m 2 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && return 0
    sleep 1
  done
  log "API của $1 không trả 200 ở cổng $port"; return 1
}

# Bản đầy đủ của cơ sở dữ liệu qua plugin Barman; in tên bản khi xong.
db_backup() {
  local cluster="$1" name="$2"
  k "$cluster" -n dr-api apply -f - >/dev/null <<YAML
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: $name
  namespace: dr-api
spec:
  cluster:
    name: db
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
YAML
  k "$cluster" -n dr-api wait --for=jsonpath='{.status.phase}'=completed "backups.postgresql.cnpg.io/$name" --timeout=600s >/dev/null
}
