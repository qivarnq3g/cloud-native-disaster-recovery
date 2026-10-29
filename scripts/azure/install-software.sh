#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"; server_name="${2:-}"; recover_from="${3:-}"
check_cluster "$cluster"
[ -n "$server_name" ] || die 64 "cách dùng: install-software.sh <cluster> <server_name> [<recover_from_server>]"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$cluster"
platform="$REPO_ROOT/infra/k8s/platform"
sas_file="$PRIVATE_DIR/sas-cnpg-backup.txt"
[ -s "$sas_file" ] || die 5 "chưa có $sas_file: chạy issue-sas.sh cnpg-backup"
password_file="$PRIVATE_DIR/db-password"
[ -s "$password_file" ] || { "$DR_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(24), end="")' > "$password_file"; chmod 600 "$password_file"; }

render() {
  local tpl="$1"; shift
  local args=()
  for pair in "$@"; do args+=(-e "s|__${pair%%=*}__|${pair#*=}|g"); done
  sed "${args[@]}" "$tpl"
}

chart_for_app() {
  helm search repo "$1" --versions -o json | "$DR_PYTHON" -c \
    "import sys, json; print(next(c['version'] for c in json.load(sys.stdin) if c['app_version'].lstrip('v') == sys.argv[1]))" "$2"
}

mark install.csv "$cluster" start
helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update >/dev/null
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update >/dev/null

helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --version v1.21.2 --set crds.enabled=true --wait >/dev/null
mark install.csv "$cluster" cert_manager_ready

cnpg_chart="$(chart_for_app cnpg/cloudnative-pg 1.30.1)" || die 1 "không có chart CNPG cho 1.30.1"
helm upgrade --install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace \
  --version "$cnpg_chart" --wait >/dev/null
kubectl apply -f https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/v0.15.1/manifest.yaml >/dev/null
kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=300s >/dev/null
mark install.csv "$cluster" cnpg_ready

velero_values="$PRIVATE_DIR/velero-values-$cluster.yaml"
render "$REPO_ROOT/infra/k8s/values/velero.yaml.tpl" \
  "BACKUP_ACCOUNT=$BACKUP_ACCOUNT" "SUB=$(az account show --query id -o tsv)" "KEY=$BACKUP_ACCOUNT_KEY" > "$velero_values"
chmod 600 "$velero_values"
helm upgrade --install velero vmware-tanzu/velero -n velero --create-namespace \
  --version "${VELERO_CHART:-12.2.1}" --set image.tag="${VELERO_IMAGE:-v1.18.4}" -f "$velero_values" --wait >/dev/null
deadline=$((SECONDS + 300))
until [ "$(kubectl -n velero get backupstoragelocations.velero.io default -o jsonpath='{.status.phase}' 2>/dev/null)" = "Available" ]; do
  [ "$SECONDS" -lt "$deadline" ] || die 1 "kho Velero chưa Available sau 5 phút"
  sleep 5
done
mark install.csv "$cluster" velero_ready

kubectl create namespace dr-api --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n dr-api create secret generic japan-store-sas \
  --from-literal=ACCOUNT="$BACKUP_ACCOUNT" --from-file=SAS="$sas_file" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n dr-api create secret generic db-app-user --type=kubernetes.io/basic-auth \
  --from-literal=username=dr --from-file=password="$password_file" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
render "$platform/object-store.yaml.tpl" "BACKUP_ACCOUNT=$BACKUP_ACCOUNT" | kubectl apply -f - >/dev/null

if [ -n "$recover_from" ]; then
  render "$platform/db-recover.yaml.tpl" "SERVER=$server_name" "SOURCE_SERVER=$recover_from" | kubectl apply -f - >/dev/null
else
  render "$platform/db-new.yaml.tpl" "SERVER=$server_name" | kubectl apply -f - >/dev/null
fi
until kubectl -n dr-api get clusters.postgresql.cnpg.io/db >/dev/null 2>&1; do sleep 2; done
kubectl -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout=900s >/dev/null \
  || die 1 "cơ sở dữ liệu db chưa Ready sau 15 phút"
mark install.csv "$cluster" db_ready

kubectl apply -f "$platform/scheduled-backup.yaml" >/dev/null
kubectl apply -f "$platform/velero-schedule.yaml" >/dev/null
mark install.csv "$cluster" schedules_ready
echo "đã cài phần mềm trên $cluster, server_name $server_name${recover_from:+, khôi phục từ $recover_from}"
