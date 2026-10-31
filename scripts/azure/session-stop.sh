#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$cluster"
db="${DR_DB_NAME:-dr}"
name="stop-$(date -u +%Y%m%d%H%M)"
refresh_admin_ip "$cluster"
mark session.csv "$cluster" stop_start

backup_id="$(take_full_backup "$name")" || exit 1
mark session.csv "$cluster" full_backup_done

velero backup create "$name" --from-schedule hourly --ttl 168h0m0s --wait \
  || die 1 "bản Velero $name lỗi, giữ máy"
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed "backups.velero.io/$name" --timeout=60s \
  || die 1 "bản Velero $name không Completed, giữ máy"
mark session.csv "$cluster" velero_backup_done

query() { kubectl -n dr-api exec db-1 -c postgres -- psql -d "$db" -tAc "$1"; }
post_count="$(query "SELECT count(*) FROM posts")" || die 1 "không đếm được bài"
digest="$(query "$DIGEST_SQL")" \
  || die 1 "không tính được mã băm nội dung"

session set state=stopped "stopped_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" "full_backup=$backup_id" \
  "velero_backup=$name" "post_count=$post_count" "content_digest=$digest"

stack="$REPO_ROOT/infra/terraform/cluster"
tf_init "$stack" "cluster-$cluster.tfstate"
terraform -chdir="$stack" destroy -auto-approve -input=false \
  -var "cluster=$cluster" -var "suffix=$SFX" -var 'admin_cidrs=["0.0.0.0/32"]' \
  -var "ssh_public_key=$(cat "$SSH_KEY.pub")"
left="$(az vm list -g "rg-dr-$cluster" --query "length(@)" -o tsv)"
[ "$left" = "0" ] || die 1 "rg-dr-$cluster vẫn còn $left máy"
mark session.csv "$cluster" stopped
echo "phiên $cluster đã tắt: $post_count bài, bản $name"
