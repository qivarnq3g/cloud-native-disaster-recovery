#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-primary"
platform="$REPO_ROOT/infra/k8s/platform"
resources=secrets,configmaps,serviceaccounts,deployments.apps,services,ingresses.networking.k8s.io
resources="$resources,certificates.cert-manager.io,objectstores.barmancloud.cnpg.io"

restore() {
  local target="$1" source_server server name deadline
  source_server="$(session get server_name)"
  [ -n "$source_server" ] || die 5 "session.json chưa có server_name để khôi phục"
  server="primary-$(date -u +%Y%m%d%H%M)"
  name="ns-$(date -u +%Y%m%d%H%M%S)"
  refresh_admin_ip primary
  kubectl create namespace dr-api --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  velero restore create "$name" --from-schedule hourly --include-namespaces dr-api --include-resources "$resources" \
    --selector 'app.kubernetes.io/managed-by notin (cloudnative-pg)' --wait || die 1 "Velero khôi phục $name lỗi"
  sed -e "s|__SERVER__|$server|g" -e "s|__SOURCE_SERVER__|$source_server|g" \
    -e "s|^      source: previous\$|      source: previous\n      recoveryTarget:\n        targetTime: \"$target\"|" \
    "$platform/db-recover.yaml.tpl" | kubectl apply -f - >/dev/null || die 1 "không tạo được db"
  kubectl -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout=900s >/dev/null \
    || die 1 "db chưa Ready sau 15 phút"
  deadline=$(( $(date +%s) + ${DR_HEALTH_TIMEOUT:-300} ))
  until curl -fsS -o /dev/null https://api.dr.qivarn.id.vn/healthz; do
    [ "$(date +%s)" -lt "$deadline" ] || die 1 "/healthz chưa trả 200 sau ${DR_HEALTH_TIMEOUT:-300} s"
    sleep "${DR_POLL_SECONDS:-5}"
  done
  session set "server_name=$server"
}

if [ "${1:-}" = --restore ]; then restore "$2"; exit 0; fi

run_id="${1:-}"; target="${2:-}"
[[ "$target" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] \
  || die 64 "cách dùng: restore-namespace.sh <run_id> <target_time dạng 2026-10-30T01:02:03Z>"
run_step "$run_id" restore bash "$0" --restore "$target"
echo "đã khôi phục namespace dr-api tới $target"
