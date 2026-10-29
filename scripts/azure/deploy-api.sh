#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"; image_tag="${2:-}"
check_cluster "$cluster"
[ -n "$image_tag" ] || die 64 "cách dùng: deploy-api.sh <cluster> <image_tag>"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$cluster"
overlay="$REPO_ROOT/infra/k8s/overlays/azure"
api_name="${DR_API_NAME:-api.dr.qivarn.id.vn}"
image="ghcr.io/qivarnq3g/dr-api:$image_tag"
stack="$REPO_ROOT/infra/terraform/cluster"
tf_init "$stack" "cluster-$cluster.tfstate" >/dev/null
ip="$(terraform -chdir="$stack" output -raw public_ip)"
fqdn="$(terraform -chdir="$stack" output -raw fqdn)"
case "$cluster" in primary) image_account="$IMAGE_PRIMARY_ACCOUNT" ;; standby) image_account="$IMAGE_STANDBY_ACCOUNT" ;; esac
sas_file="$PRIVATE_DIR/sas-api-images-$cluster.txt"
[ -s "$sas_file" ] || die 5 "chưa có $sas_file: chạy issue-sas.sh api-images-$cluster"
code_file="$PRIVATE_DIR/secret-code"
[ -s "$code_file" ] || { "$DR_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(18), end="")' > "$code_file"; chmod 600 "$code_file"; }
mark deploy.csv "$cluster" start

apply_secret() { kubectl -n dr-api create secret generic "$@" --dry-run=client -o yaml | kubectl apply -f - >/dev/null; }
apply_secret image-store --from-literal=AZURE_STORAGE_ACCOUNT_NAME="$image_account" --from-file=AZURE_STORAGE_SAS_KEY="$sas_file"
apply_secret api-secret-code --from-file=SECRET_CODE="$code_file"
kubectl -n dr-api create configmap api-site --from-literal=CLUSTER="$cluster" --from-literal=REGION="$CLUSTER_REGION" \
  --from-literal=IMAGE_STORE_CONTAINER=images --from-literal=IMAGE_STORE_READ_ONLY="${DR_READ_ONLY:-false}" \
  --from-literal=TRUSTED_PROXIES=10.42.0.0/16 --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -f "$REPO_ROOT/infra/k8s/platform/cluster-issuers.yaml" >/dev/null

restored=
latest="$(kubectl -n velero get backups.velero.io -o json | "$DR_PYTHON" -c '
import json, sys
done = [b for b in json.load(sys.stdin)["items"] if b.get("status", {}).get("phase") == "Completed"]
done.sort(key=lambda b: b["status"].get("completionTimestamp", ""))
print(done[-1]["metadata"]["name"] if done else "")')"
if [ -n "$latest" ] && ! kubectl -n dr-api get secret api-tls >/dev/null 2>&1; then
  restore="tls-$(date -u +%Y%m%d%H%M%S)"
  velero restore create "$restore" --from-backup "$latest" \
    --include-resources secrets,certificates.cert-manager.io --selector app.kubernetes.io/part-of=dr-api-tls --wait >/dev/null \
    || die 1 "khôi phục chứng chỉ từ $latest lỗi"
  phase="$(kubectl -n velero get "restores.velero.io/$restore" -o jsonpath='{.status.phase}')"
  [ "$phase" = "Completed" ] || die 1 "khôi phục $restore đang $phase"
  if kubectl -n dr-api get secret api-tls >/dev/null 2>&1; then restored="$latest"; fi
fi
mark deploy.csv "$cluster" tls_restored

if [ -s "$PRIVATE_DIR/ghcr-token" ]; then
  kubectl -n dr-api create secret docker-registry ghcr-pull --docker-server=ghcr.io \
    --docker-username=qivarnq3g --docker-password="$(cat "$PRIVATE_DIR/ghcr-token")" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
else
  crane_dir="$(mktemp -d)"
  trap 'rm -rf "$crane_dir"' EXIT
  gh auth token | DOCKER_CONFIG="$crane_dir" crane auth login ghcr.io -u qivarnq3g --password-stdin >/dev/null 2>&1 \
    || die 1 "không đăng nhập được ghcr.io bằng gh"
  DOCKER_CONFIG="$crane_dir" crane pull --platform linux/amd64 "$image" "$crane_dir/image.tar" || die 1 "không kéo được $image"
  rm -rf "$crane_dir/config.json"
  ssh -i "$SSH_KEY" -o UserKnownHostsFile="$PRIVATE_DIR/known_hosts" -o StrictHostKeyChecking=accept-new "dr@$fqdn" \
    'sudo k3s ctr -n k8s.io images import -' < "$crane_dir/image.tar" >/dev/null || die 1 "không nạp được ảnh vào k3s"
fi
mark deploy.csv "$cluster" image_ready

kubectl kustomize "$overlay" | sed "s|ghcr.io/qivarnq3g/dr-api:main|$image|" | kubectl apply -f - >/dev/null
kubectl -n dr-api rollout status deploy/api --timeout=300s || die 1 "API chưa chạy được sau 5 phút"
mark deploy.csv "$cluster" api_rolled_out

resolved="$("$DR_PYTHON" -c 'import socket, sys; print(socket.gethostbyname(sys.argv[1]))' "$api_name" 2>/dev/null || true)"
if [ "$resolved" = "$ip" ]; then
  kubectl apply -f "$overlay/certificate.yaml" >/dev/null
  kubectl -n dr-api wait --for=condition=Ready certificates.cert-manager.io/api-tls --timeout=600s >/dev/null \
    || die 1 "chứng chỉ api-tls chưa Ready sau 10 phút"
  mark deploy.csv "$cluster" certificate_ready
else
  echo "$api_name đang trỏ ${resolved:-không đâu}, chưa phải $ip: chưa xin chứng chỉ"
fi
echo "API $cluster chạy $image${restored:+, chứng chỉ khôi phục từ $restored}"
