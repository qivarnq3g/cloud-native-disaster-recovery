#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
py="${DR_PYTHON:-python}"
out_dir="${DRILL_OUT_DIR:-$repo/data/daily-drill}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
: "${DRILL_READ_SAS_JSON:?thiếu DRILL_READ_SAS_JSON}" "${DRILL_VELERO_KEY:?thiếu DRILL_VELERO_KEY}"
export KUBECONFIG="$work/kubeconfig"

mkdir -p "$out_dir"
csv="$out_dir/$(date -u +%Y-%m-%d).csv"
[ -f "$csv" ] || echo "step,started_at,ended_at,result" > "$csv"
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
step() {
  local name="$1" started rc
  shift
  started="$(now)"
  set +e
  (set -e; "$@")
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then echo "$name,$started,$(now),ok" >> "$csv"; else echo "$name,$started,$(now),fail" >> "$csv"; exit "$rc"; fi
}

sas_field() {
  "$py" -c '
import json, os, sys
for url, token in json.loads(os.environ["DRILL_READ_SAS_JSON"]).items():
    parts = url.rstrip("/").split("/")
    if parts[-1] == sys.argv[2] and parts[2].startswith(sys.argv[1]):
        print(parts[2].split(".")[0] if sys.argv[3] == "account" else token.lstrip("?"))
        sys.exit(0)
sys.exit(f"DRILL_READ_SAS_JSON thiếu {sys.argv[1]}*/{sys.argv[2]}")' "$1" "$2" "$3"
}

session_field() {
  "$py" -c '
import json, os, sys
from scripts.dr.backup_check import _container, _pick
from scripts.dr.session_state import read_session
s = read_session(_container(*_pick(json.loads(os.environ["DRILL_READ_SAS_JSON"]), "drbackup", "status")))
if s is None:
    sys.exit("không đọc được status/session.json")
print(getattr(s, sys.argv[1]) or "")' "$1"
}

render() {
  local tpl="$1"
  shift
  local args=()
  for pair in "$@"; do args+=(-e "s|__${pair%%=*}__|${pair#*=}|g"); done
  sed "${args[@]}" "$tpl"
}

chart_for_app() {
  helm search repo "$1" --versions -o json | "$py" -c \
    "import sys, json; print(next(c['version'] for c in json.load(sys.stdin) if c['app_version'].lstrip('v') == sys.argv[1]))" "$2"
}

cd "$repo"
backup_account="$(sas_field drbackup cnpg account)"
copy_account="$(sas_field drimgcopy images account)"
state="$(session_field state)"
server_name="$(session_field server_name)"
velero_backup="$(session_field velero_backup)"
echo "phiên $state, server_name $server_name, kho $backup_account, ảnh từ $copy_account"
"$py" -m scripts.dr.verify_restore --list-store "$work/store-before.txt"

kind_up() {
  kind create cluster --config infra/k8s/drill/kind-config.yaml --kubeconfig "$KUBECONFIG" --wait 180s
}

install() {
  helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
  helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update >/dev/null
  helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update >/dev/null
  helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
    --version v1.21.2 --set crds.enabled=true --wait >/dev/null
  helm upgrade --install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace \
    --version "$(chart_for_app cnpg/cloudnative-pg 1.30.1)" --wait >/dev/null
  kubectl apply -f https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/v0.15.1/manifest.yaml >/dev/null
  kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=300s >/dev/null
  render infra/k8s/values/velero-drill.yaml.tpl "BACKUP_ACCOUNT=$backup_account" "KEY=$DRILL_VELERO_KEY" > "$work/velero.yaml"
  helm upgrade --install velero vmware-tanzu/velero -n velero --create-namespace \
    --version 12.2.1 --set image.tag=v1.18.4 -f "$work/velero.yaml" --wait >/dev/null
  local deadline=$((SECONDS + 300))
  until [ "$(kubectl -n velero get backupstoragelocations.velero.io default -o jsonpath='{.status.phase}' 2>/dev/null)" = "Available" ]; do
    [ "$SECONDS" -lt "$deadline" ] || { echo "kho Velero chưa Available sau 5 phút" >&2; return 1; }
    sleep 5
  done
}

newest_hourly() {
  kubectl -n velero get backups.velero.io -l velero.io/schedule-name=hourly -o json | "$py" -c '
import json, sys
done = [b for b in json.load(sys.stdin)["items"] if b.get("status", {}).get("phase") == "Completed"]
done.sort(key=lambda b: b["status"].get("completionTimestamp", ""))
print(done[-1]["metadata"]["name"] if done else "")'
}

velero_restore() {
  local backup="$velero_backup" deadline=$((SECONDS + 300))
  until { [ "$state" = "stopped" ] && kubectl -n velero get "backups.velero.io/$backup" >/dev/null 2>&1; } \
    || { [ "$state" != "stopped" ] && backup="$(newest_hourly)" && [ -n "$backup" ]; }; do
    [ "$SECONDS" -lt "$deadline" ] || { echo "Velero chưa thấy bản ${backup:-hourly} sau 5 phút" >&2; return 1; }
    sleep 5
  done
  echo "khôi phục Velero từ $backup"
  local name
  name="drill-$(date -u +%Y%m%d%H%M%S)"
  velero restore create "$name" --from-backup "$backup" --include-namespaces dr-api \
    --include-resources secrets,configmaps,serviceaccounts,deployments.apps,services --wait
  [ "$(kubectl -n velero get "restores.velero.io/$name" -o jsonpath='{.status.phase}')" = "Completed" ]
  kubectl -n dr-api get secrets,services,configmaps -o json | "$py" -c '
import json, sys
for o in json.load(sys.stdin)["items"]:
    if any(r.get("kind") == "Cluster" and r.get("apiVersion", "").startswith("postgresql.cnpg.io/")
           for r in o["metadata"].get("ownerReferences", [])):
        print("{}/{}".format(o["kind"].lower(), o["metadata"]["name"]))' > "$work/cnpg-owned.txt"
  if [ -s "$work/cnpg-owned.txt" ]; then xargs kubectl -n dr-api delete < "$work/cnpg-owned.txt"; fi
  kubectl -n dr-api scale deploy/api --replicas=0
  kubectl -n dr-api create secret generic japan-store-sas --from-literal=ACCOUNT="$backup_account" \
    --from-literal=SAS="$(sas_field drbackup cnpg token)" --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n dr-api create secret generic image-store --from-literal=AZURE_STORAGE_ACCOUNT_NAME="$copy_account" \
    --from-literal=AZURE_STORAGE_SAS_KEY="$(sas_field drimgcopy images token)" --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n dr-api create configmap api-site --from-literal=CLUSTER=standby --from-literal=REGION=drill \
    --from-literal=IMAGE_STORE_CONTAINER=images --from-literal=IMAGE_STORE_READ_ONLY=true \
    --from-literal=TRUSTED_PROXIES=10.244.0.0/16 --dry-run=client -o yaml | kubectl apply -f -
}

db_restore() {
  render infra/k8s/platform/object-store.yaml.tpl "BACKUP_ACCOUNT=$backup_account" | kubectl apply -f -
  render infra/k8s/drill/db-recover.yaml.tpl "SOURCE_SERVER=$server_name" | kubectl apply -f -
  until kubectl -n dr-api get clusters.postgresql.cnpg.io/db >/dev/null 2>&1; do sleep 2; done
  kubectl -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout=900s
}

api_up() {
  local image
  image="$(kubectl -n dr-api get deploy/api -o jsonpath='{.spec.template.spec.containers[0].image}')"
  docker pull --quiet "$image"
  kind load docker-image --name drill "$image"
  kubectl -n dr-api scale deploy/api --replicas=1
  kubectl -n dr-api rollout status deploy/api --timeout=300s
  kubectl -n dr-api port-forward svc/api 8080:80 > "$work/port-forward.log" 2>&1 &
  echo $! > "$work/port-forward.pid"
  local deadline=$((SECONDS + 60))
  until curl -fsS http://127.0.0.1:8080/healthz; do
    [ "$SECONDS" -lt "$deadline" ] || { echo "API trong kind không trả /healthz" >&2; return 1; }
    sleep 2
  done
  echo
}

verify() {
  "$py" -m scripts.dr.verify_restore --api http://127.0.0.1:8080 \
    --psql "kubectl -n dr-api exec db-1 -c postgres -- psql -d dr -tAc" --sample "${DRILL_SAMPLE:-50}" \
    --store-before "$work/store-before.txt"
}

step kind_up kind_up
step install install
step velero_restore velero_restore
step db_restore db_restore
step api_up api_up
step verify verify
kill "$(cat "$work/port-forward.pid")" 2>/dev/null || true
echo "diễn tập xong: $csv"
