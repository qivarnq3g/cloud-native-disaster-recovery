#!/usr/bin/env bash
# Dựng một cụm kind và cài phần mềm sao lưu: cert-manager, CNPG, Barman Cloud Plugin, Velero.
# Dùng: create-cluster.sh <primary|standby>. Ghi mốc thời gian vào data/kind/up.csv.
source "$(dirname "$0")/lib.sh"
NAME="$1"
[ "$NAME" = primary ] || [ "$NAME" = standby ] || { log "tên cụm phải là primary hoặc standby"; exit 64; }

create() {
  sed "s/__HOST_PORT__/$(port_of "$NAME")/" "$ROOT/infra/kind/cluster.yaml.tpl" > "$STATE_DIR/kind-$NAME.yaml"
  kind create cluster --name "$NAME" --config "$STATE_DIR/kind-$NAME.yaml" --wait 300s 2>"$STATE_DIR/kind-$NAME.log" \
    || { cat "$STATE_DIR/kind-$NAME.log" >&2; return 1; }
}

load_images() {
  # Tệp gói image do up.sh tạo (image_archive trong lib.sh); kind load docker-image lỗi với
  # kho image containerd của Docker 29 khi image có nhiều nền tảng.
  kind load image-archive --name "$NAME" "$(image_archive)" >/dev/null
}

install_software() {
  helm upgrade --install cert-manager jetstack/cert-manager --kube-context "$(ctx "$NAME")" -n cert-manager \
    --create-namespace --version "$CERT_MANAGER_VERSION" -f "$ROOT/infra/kind/values/cert-manager.yaml" --wait >/dev/null
  helm upgrade --install cnpg cnpg/cloudnative-pg --kube-context "$(ctx "$NAME")" -n cnpg-system \
    --create-namespace --version "$CNPG_CHART_VERSION" --wait >/dev/null
  k "$NAME" apply --server-side -f "$ROOT/infra/kind/vendor/plugin-barman-cloud-$BARMAN_VERSION.yaml" >/dev/null
  sed -e "s|__ACCESS_KEY__|$(cred velero access)|" -e "s|__SECRET_KEY__|$(cred velero secret)|" \
    "$ROOT/infra/kind/values/velero.yaml.tpl" > "$STATE_DIR/velero-values-$NAME.yaml"
  helm upgrade --install velero vmware-tanzu/velero --kube-context "$(ctx "$NAME")" -n velero \
    --create-namespace --version "$VELERO_CHART_VERSION" -f "$STATE_DIR/velero-values-$NAME.yaml" --wait >/dev/null
  k "$NAME" -n cnpg-system rollout status deploy/barman-cloud --timeout=300s >/dev/null
  for _ in $(seq 1 60); do
    [ "$(k "$NAME" -n velero get backupstoragelocations.velero.io default -o jsonpath='{.status.phase}' 2>/dev/null)" = Available ] && return 0
    sleep 2
  done
  log "BackupStorageLocation của Velero ở $NAME không Available"; return 1
}

timed "$NAME" kind_create create
timed "$NAME" load_images load_images
timed "$NAME" install_software install_software
log "$NAME: cụm và phần mềm sẵn sàng"
