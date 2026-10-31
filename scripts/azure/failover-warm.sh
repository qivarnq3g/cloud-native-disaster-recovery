#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-standby"

promote() {
  refresh_admin_ip standby
  kubectl -n dr-api patch clusters.postgresql.cnpg.io/db --type merge -p '{"spec":{"replica":{"enabled":false}}}' >/dev/null \
    || die 1 "không tắt được chế độ bản sao của db"
  local deadline=$(( $(date +%s) + ${DR_PROMOTE_TIMEOUT:-600} ))
  until [ "$(kubectl -n dr-api exec db-1 -c postgres -- psql -d dr -tAc 'SELECT pg_is_in_recovery()' 2>/dev/null)" = f ]; do
    [ "$(date +%s)" -lt "$deadline" ] || die 1 "db chưa thành cụm chính sau ${DR_PROMOTE_TIMEOUT:-600} s"
    sleep "${DR_POLL_SECONDS:-5}"
  done
  remove_image_replication
  kubectl -n dr-api patch configmap api-site --type merge -p '{"data":{"IMAGE_STORE_READ_ONLY":"false"}}' >/dev/null \
    || die 1 "không bật được ghi ảnh"
  kubectl -n dr-api rollout restart deploy/api >/dev/null || die 1 "không khởi động lại được API"
  kubectl -n dr-api rollout status deploy/api --timeout=300s >/dev/null || die 1 "API chưa chạy lại sau 300 s"
}

case "${1:-}" in
  --promote) promote; exit 0 ;;
  --switch)
    server="$(cat "$PRIVATE_DIR/standby-server" 2>/dev/null || true)"
    [ -n "$server" ] || die 5 "chưa có $PRIVATE_DIR/standby-server: dựng bằng standby-up.sh"
    switch_to standby "$server"; exit 0 ;;
esac

run_id="${1:-}"
[ "$(session get cluster)" != standby ] || die 3 "cụm dự phòng đã là cụm chính của phiên"
vm_exists standby || die 5 "chưa có vm-dr-standby: dựng bằng standby-up.sh"
run_step "$run_id" restore bash "$0" --promote
run_step "$run_id" switch bash "$0" --switch
echo "đã chuyển sang cụm dự phòng ấm"
