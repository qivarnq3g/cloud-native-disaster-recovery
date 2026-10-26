#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
PROFILE=full
SEED="${SEED_POSTS:-1000}"
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    *) log "không hiểu $1"; exit 64 ;;
  esac
done
[ "$PROFILE" = full ] || [ "$PROFILE" = primary ] || { log "--profile phải là full hoặc primary"; exit 64; }

for tool in docker kind kubectl helm curl "$PYTHON"; do
  command -v "$tool" >/dev/null || { log "thiếu $tool, xem scripts/kind/README.md"; exit 1; }
done
"$PYTHON" -c 'import boto3' 2>/dev/null || { log "thiếu boto3: pip install -r scripts/kind/requirements.txt"; exit 1; }
if kind get clusters 2>/dev/null | grep -qx 'primary\|standby' || docker inspect dr-seaweedfs >/dev/null 2>&1; then
  log "môi trường cũ còn đó, chạy scripts/kind/down.sh trước"; exit 1
fi

prepare_images() {
  for img in "$SEAWEEDFS_IMAGE" "$RCLONE_IMAGE"; do
    docker image inspect "$img" >/dev/null 2>&1 || docker pull -q "$img" >/dev/null
  done
  if ! docker image inspect "$API_IMAGE" >/dev/null 2>&1; then
    log "build image API từ app/api (lần đầu mất vài phút)"
    docker build -q -t "$API_IMAGE" --build-arg APP_VERSION="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo dev)" "$ROOT/app/api" >/dev/null
  fi
  image_archive >/dev/null
  helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
  helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update >/dev/null
  helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update >/dev/null
}

start_store() {
  "$PYTHON" -m scripts.kind.store init "$STATE_DIR"
  docker network inspect kind >/dev/null 2>&1 || docker network create kind >/dev/null
  docker run -d --name dr-seaweedfs --network kind -p "127.0.0.1:$S3_PORT:8333" \
    -v "$STATE_DIR/s3.json:/etc/seaweedfs/s3.json:ro" "$SEAWEEDFS_IMAGE" \
    server -s3 -s3.config=/etc/seaweedfs/s3.json -dir=/data -master.volumeSizeLimitMB=64 >/dev/null
  "$PYTHON" -m scripts.kind.store buckets "$STATE_DIR"
  docker run -d --name dr-image-copy --network kind --entrypoint sh \
    -e RCLONE_CONFIG_SW_TYPE=s3 -e RCLONE_CONFIG_SW_PROVIDER=SeaweedFS \
    -e RCLONE_CONFIG_SW_ENDPOINT=http://dr-seaweedfs:8333 \
    -e RCLONE_CONFIG_SW_ACCESS_KEY_ID="$(cred image-copy access)" \
    -e RCLONE_CONFIG_SW_SECRET_ACCESS_KEY="$(cred image-copy secret)" \
    "$RCLONE_IMAGE" -c 'while true; do
      for dst in images-copy images-standby; do rclone copy sw:images "sw:$dst" --s3-no-check-bucket -q; done
      sleep 2; done' >/dev/null
}

primary_app() {
  local server; server="$(new_server_name primary)"
  echo "$server" > "$STATE_DIR/server-primary"
  site_config primary images false
  k primary apply -f "$ROOT/infra/kind/platform/object-store.yaml" >/dev/null
  apply_tpl primary "$ROOT/infra/kind/platform/db-new.yaml.tpl" "SERVER=$server" >/dev/null
  wait_db primary >/dev/null
  deploy_api primary >/dev/null
  wait_healthy primary
  db_backup primary "base-$(date -u +%Y%m%d%H%M%S)"
}

standby_app() {
  local server; server="$(new_server_name standby)"
  echo "$server" > "$STATE_DIR/server-standby"
  site_config standby images-standby false
  k standby apply -f "$ROOT/infra/kind/platform/object-store.yaml" >/dev/null
  apply_tpl standby "$ROOT/infra/kind/platform/db-replica.yaml.tpl" \
    "SERVER=$server" "SOURCE_SERVER=$(cat "$STATE_DIR/server-primary")" >/dev/null
  wait_db standby >/dev/null
  k standby apply -k "$ROOT/infra/k8s/overlays/kind" >/dev/null
  k standby -n dr-api scale deploy/api --replicas=0 >/dev/null
}

seed() {
  "$PYTHON" -m scripts.kind.workload seed --api "http://127.0.0.1:$PRIMARY_PORT" \
    --code-file "$STATE_DIR/secret-code" --ledger "$STATE_DIR/ledger.csv" --count "$SEED"
}

mkdir -p "$STATE_DIR" "$DATA_DIR"
timed host prepare_images prepare_images
timed host object_store start_store
pids=()
"$ROOT/scripts/kind/create-cluster.sh" primary & pids+=($!)
if [ "$PROFILE" = full ]; then "$ROOT/scripts/kind/create-cluster.sh" standby & pids+=($!); fi
for p in "${pids[@]}"; do wait "$p"; done
timed primary app primary_app
if [ "$PROFILE" = full ]; then timed standby app standby_app; fi
timed primary seed seed
echo "$PROFILE" > "$STATE_DIR/profile"
log "xong: API cụm chính http://127.0.0.1:$PRIMARY_PORT$([ "$PROFILE" = full ] && echo ", cụm dự phòng http://127.0.0.1:$STANDBY_PORT")"
