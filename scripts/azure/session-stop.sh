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

velero_backup_from_schedule "$name" "${DR_STOP_BACKUP_TTL:-720h0m0s}" || die 1 "bản Velero $name lỗi, giữ máy"
kubectl -n velero wait --for=jsonpath='{.status.phase}'=Completed "backups.velero.io/$name" --timeout=600s \
  || die 1 "bản Velero $name không Completed, giữ máy"
mark session.csv "$cluster" velero_backup_done

query() { kubectl -n dr-api exec db-1 -c postgres -- psql -d "$db" -tAc "$1"; }
post_count="$(query "SELECT count(*) FROM posts")" || die 1 "không đếm được bài"
digest="$(query "$DIGEST_SQL")" \
  || die 1 "không tính được mã băm nội dung"

recipients="${DR_VAULT_RECIPIENTS:-$REPO_ROOT/infra/k8s/platform/vault-recipients.txt}"
[ -s "$recipients" ] || die 1 "chưa có $recipients (khóa công khai age), giữ máy"
server="$(session get server_name)"
server="${server%$'\r'}"
[ -n "$server" ] || die 1 "không đọc được server_name, giữ máy"
case "$cluster" in
  primary) image_account="$IMAGE_PRIMARY_ACCOUNT" ;;
  standby) image_account="$IMAGE_STANDBY_ACCOUNT" ;;
esac
velero_url="https://$BACKUP_ACCOUNT.blob.core.windows.net/velero"
velero_sas="$(sed -n "s|.*\"$velero_url\":\"\([^\"]*\)\".*|\1|p" "$PRIVATE_DIR/sas-check-read.txt")"
[ -n "$velero_sas" ] || die 1 "sas-check-read.txt không có mã đọc $velero_url, giữ máy"
vault_job="vault-${name#stop-}"
apply_object() { kubectl -n dr-api create "$@" --dry-run=client -o yaml | kubectl apply -f - >/dev/null; }
apply_object configmap vault-code --from-file="$REPO_ROOT/scripts/vault/__init__.py" \
  --from-file="$REPO_ROOT/scripts/vault/blob.py" --from-file="$REPO_ROOT/scripts/vault/pack.py" \
  --from-file=vault-recipients.txt="$recipients" || die 1 "không tạo được ConfigMap vault-code, giữ máy"
apply_object configmap vault-config "--from-literal=SERVER_NAME=$server" "--from-literal=POST_COUNT=$post_count" \
  "--from-literal=CONTENT_DIGEST=$digest" "--from-literal=VELERO_BACKUP=$name" \
  "--from-literal=AGE_SHA256=$AGE_SHA256" \
  "--from-literal=VAULT_CONTAINER_URL=https://$VAULT_ACCOUNT.blob.core.windows.net/vault" \
  "--from-literal=IMAGE_CONTAINER_URL=https://$image_account.blob.core.windows.net/images" \
  "--from-literal=VELERO_CONTAINER_URL=$velero_url" || die 1 "không tạo được ConfigMap vault-config, giữ máy"
apply_object secret generic vault-sas "--from-literal=VAULT_SAS=$(cat "$PRIVATE_DIR/sas-vault-writer.txt")" \
  "--from-literal=IMAGE_SAS=$(cat "$PRIVATE_DIR/sas-api-images-$cluster.txt")" \
  "--from-literal=VELERO_SAS=$velero_sas" || die 1 "không tạo được secret vault-sas, giữ máy"
sed "s|__NAME__|$vault_job|g" "$REPO_ROOT/infra/k8s/platform/vault-pack.yaml.tpl" | kubectl apply -f - >/dev/null \
  || die 1 "không tạo được job $vault_job, giữ máy"
if ! kubectl -n dr-api wait --for=condition=complete "job/$vault_job" --timeout=1800s; then
  kubectl -n dr-api logs "job/$vault_job" --all-containers --tail=30 >&2 || true
  die 1 "job két $vault_job lỗi, giữ máy"
fi
vault_pack="$(kubectl -n dr-api logs "job/$vault_job" -c pack --tail=1)"
vault_pack="${vault_pack%$'\r'}"
[[ "$vault_pack" == "$server/"*.tar.age ]] || die 1 "job két không in tên gói hợp lệ: $vault_pack"
mark session.csv "$cluster" vault_done

session set state=stopped "stopped_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" "full_backup=$backup_id" \
  "velero_backup=$name" "post_count=$post_count" "content_digest=$digest" "vault_pack=$vault_pack"

stack="$REPO_ROOT/infra/terraform/cluster"
tf_init "$stack" "cluster-$cluster.tfstate"
terraform -chdir="$stack" destroy -auto-approve -input=false \
  -var "cluster=$cluster" -var "suffix=$SFX" -var 'admin_cidrs=["0.0.0.0/32"]' \
  -var "ssh_public_key=$(cat "$SSH_KEY.pub")"
left="$(az vm list -g "rg-dr-$cluster" --query "length(@)" -o tsv)"
[ "$left" = "0" ] || die 1 "rg-dr-$cluster vẫn còn $left máy"
mark session.csv "$cluster" stopped
echo "phiên $cluster đã tắt: $post_count bài, bản $name"
