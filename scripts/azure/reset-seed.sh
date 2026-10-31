#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"
seed_file="$PRIVATE_DIR/seed.json"
[ -s "$seed_file" ] || die 5 "chưa có $seed_file: tạo mẫu bằng seed.sh"
[ "$(session get state)" = running ] && [ "$(session get cluster)" = "$cluster" ] \
  || die 3 "$cluster không phải cụm đang phục vụ của phiên"
seed_get() { "$DR_PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$seed_file" "$1"; }
backup_id="$(seed_get backup_id)"; source_server="$(seed_get server_name)"
want_count="$(seed_get post_count)"; want_digest="$(seed_get content_digest)"

export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$cluster"
server="$cluster-$(date -u +%Y%m%d%H%M)"
refresh_admin_ip "$cluster"
mark seed.csv "$cluster" reset_start
kubectl -n dr-api delete clusters.postgresql.cnpg.io/db --ignore-not-found --wait=true --timeout=300s >/dev/null \
  || die 1 "không xóa được db"
sed -e "s|__SERVER__|$server|g" -e "s|__SOURCE_SERVER__|$source_server|g" -e "s|__BACKUP_ID__|$backup_id|g" \
  "$REPO_ROOT/infra/k8s/platform/db-recover-to-backup.yaml.tpl" | kubectl apply -f - >/dev/null || die 1 "không tạo được db"
kubectl -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout=900s >/dev/null \
  || die 1 "db chưa Ready sau 15 phút"
kubectl -n dr-api rollout restart deploy/api >/dev/null || die 1 "không khởi động lại được API"
kubectl -n dr-api rollout status deploy/api --timeout=300s >/dev/null || die 1 "API chưa chạy lại sau 300 s"

query() { kubectl -n dr-api exec db-1 -c postgres -- psql -d dr -tAc "$1"; }
count="$(query "SELECT count(*) FROM posts")" || die 1 "không đếm được bài"
digest="$(query "$DIGEST_SQL")" || die 1 "không tính được mã băm nội dung"
[ "$count" = "$want_count" ] && [ "$digest" = "$want_digest" ] \
  || die 1 "sau khi đưa về mẫu có $count bài, mã băm $digest; mẫu là $want_count bài, $want_digest"
cp "$PRIVATE_DIR/seed-ledger.csv" "$PRIVATE_DIR/drill-ledger.csv"
session set "server_name=$server" "post_count=$count" "content_digest=$digest"
mark seed.csv "$cluster" reset_done
echo "đã đưa $cluster về mẫu: $count bài, server_name $server"
