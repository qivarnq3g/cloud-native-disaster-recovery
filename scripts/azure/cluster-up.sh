#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"

stack="$REPO_ROOT/infra/terraform/cluster"
mark cluster-build.csv "$cluster" start
tf_init "$stack" "cluster-$cluster.tfstate" >/dev/null
terraform -chdir="$stack" apply -auto-approve -input=false \
  -var "cluster=$cluster" -var "suffix=$SFX" \
  -var "admin_cidrs=[\"${ADMIN_IP:-$(curl -fsS https://api.ipify.org)}/32\"]" \
  -var "ssh_public_key=$(cat "$SSH_KEY.pub")"
fqdn="$(terraform -chdir="$stack" output -raw fqdn)"
mark cluster-build.csv "$cluster" vm_created

ssh_opts=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$PRIVATE_DIR/known_hosts" -o ConnectTimeout=5)
ssh-keygen -q -R "$fqdn" -f "$PRIVATE_DIR/known_hosts" >/dev/null 2>&1 || true
deadline=$((SECONDS + 900))
until ssh "${ssh_opts[@]}" "dr@$fqdn" 'sudo test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; do
  [ "$SECONDS" -lt "$deadline" ] || die 1 "sau 15 phút k3s trên $fqdn vẫn chưa cài xong"
  sleep 5
done
mark cluster-build.csv "$cluster" k3s_installed

kubeconfig="$PRIVATE_DIR/kubeconfig-$cluster"
ssh "${ssh_opts[@]}" "dr@$fqdn" 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed "s/127.0.0.1/$fqdn/" > "$kubeconfig"
chmod 600 "$kubeconfig"
export KUBECONFIG="$kubeconfig"
until kubectl wait --for=condition=Ready node --all --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark cluster-build.csv "$cluster" node_ready
until kubectl -n kube-system rollout status deploy/traefik --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark cluster-build.csv "$cluster" traefik_ready
echo "cụm $cluster sẵn sàng: $fqdn"
