#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
target="${DR_SEED_COUNT:-1000}"
ledger="$PRIVATE_DIR/seed-ledger.csv"

[ "$(session get state)" = running ] || die 3 "phiên chưa chạy: bật bằng session-start.sh trước"
cluster="$(session get cluster)"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$cluster"
refresh_admin_ip "$cluster"
query() { kubectl -n dr-api exec db-1 -c postgres -- psql -d dr -tAc "$1"; }

done_rows=0
[ ! -s "$ledger" ] || done_rows=$(( $(wc -l < "$ledger") - 1 ))
posts="$(query "SELECT count(*) FROM posts")" || die 1 "không đếm được bài"
[ "$done_rows" -gt 0 ] || [ "$posts" -lt 100 ] || die 3 "cơ sở dữ liệu đã có $posts bài, không tạo mẫu chồng lên"

started=$(date +%s)
if [ "$done_rows" -lt "$target" ]; then
  (cd "$REPO_ROOT" && "$DR_PYTHON" -m scripts.kind.workload seed --api https://api.dr.qivarn.id.vn \
    --code-file "$PRIVATE_DIR/secret-code" --ledger "$ledger" --count $(( target - done_rows ))) \
    || die 1 "đăng bài mẫu lỗi; chạy lại seed.sh sẽ đăng tiếp từ sổ $ledger"
fi
posted_s=$(( $(date +%s) - started ))

name="seed-$(date -u +%Y%m%d%H%M)"
backup_id="$(take_full_backup "$name")" || exit 1
ended_at="$(kubectl -n dr-api get "backups.postgresql.cnpg.io/$name" -o jsonpath='{.status.stoppedAt}')"
post_count="$(query "SELECT count(*) FROM posts")" || die 1 "không đếm được bài"
digest="$(query "$DIGEST_SQL")" || die 1 "không tính được mã băm nội dung"
"$DR_PYTHON" -c 'import json, sys; keys = ["backup_id", "server_name", "post_count", "content_digest", "ended_at"]; json.dump(dict(zip(keys, sys.argv[2:])), open(sys.argv[1], "w"), indent=2)' \
  "$PRIVATE_DIR/seed.json" "$backup_id" "$(session get server_name)" "$post_count" "$digest" "$ended_at"
mark seed.csv "$cluster" seeded
echo "đã tạo mẫu: $post_count bài, đăng mất $posted_s s, bản đầy đủ $backup_id"
