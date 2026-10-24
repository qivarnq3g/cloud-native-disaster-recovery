#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
NAME="$1"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$NAME"
KEY="$(cat "$PRIVATE_DIR/key-$BACKUP_ACCOUNT")"
SUB="$(az account show --query id -o tsv)"
helm repo add jetstack https://charts.jetstack.io --force-update >/dev/null
helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update >/dev/null
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update >/dev/null
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --version v1.21.2 --set crds.enabled=true --wait
CHART_CNPG="$(helm search repo cnpg/cloudnative-pg --versions -o json | python -c "import sys,json; print(next(c['version'] for c in json.load(sys.stdin) if c['app_version']=='1.30.1'))")"
helm upgrade --install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace --version "$CHART_CNPG" --wait
kubectl apply -f https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/v0.15.1/manifest.yaml
kubectl -n cnpg-system rollout status deploy/barman-cloud --timeout=300s
sed -e "s/__BACKUP_ACCOUNT__/$BACKUP_ACCOUNT/" -e "s/__SUB__/$SUB/" -e "s|__KEY__|$KEY|" \
  infra/trial/velero-values.yaml.tpl > "$PRIVATE_DIR/velero-values-$NAME.yaml"
helm upgrade --install velero vmware-tanzu/velero -n velero --create-namespace \
  -f "$PRIVATE_DIR/velero-values-$NAME.yaml" --wait
kubectl -n velero get backupstoragelocation default -o jsonpath='{.status.phase}{"\n"}'
