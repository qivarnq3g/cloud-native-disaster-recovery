#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
NAME="$1"; RG="$2"; DNS="$3"; FQDN="$4"
MY_IP="$(curl -s https://api.ipify.org)"
CI="$PRIVATE_DIR/cloud-init-$NAME.yaml"
sed "s/__FQDN__/$FQDN/" infra/trial/cloud-init-k3s.yaml.tpl > "$CI"
mark() { echo "$NAME,$1,$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$DATA_DIR/cluster-build.csv"; }
[ -f "$DATA_DIR/cluster-build.csv" ] || echo "cluster,mark,time_utc" > "$DATA_DIR/cluster-build.csv"
mark start
az vm create -g "$RG" -n "vm-$NAME" -l "$CLUSTER_REGION" --image Ubuntu2404 --size Standard_B2als_v2 \
  --admin-username dr --ssh-key-values "$SSH_KEY.pub" --public-ip-sku Standard \
  --public-ip-address-dns-name "$DNS" --custom-data "$CI" --nsg-rule NONE \
  --os-disk-size-gb 32 --storage-sku Premium_LRS -o none
mark vm_created
az network nsg rule create -g "$RG" --nsg-name "vm-${NAME}NSG" -n admin --priority 100 \
  --source-address-prefixes "$MY_IP/32" --destination-port-ranges 22 6443 --access Allow --protocol Tcp -o none
az network nsg rule create -g "$RG" --nsg-name "vm-${NAME}NSG" -n web --priority 110 \
  --source-address-prefixes Internet --destination-port-ranges 80 443 --access Allow --protocol Tcp -o none
until ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 "dr@$FQDN" 'sudo test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; do sleep 5; done
mark k3s_installed
ssh -i "$SSH_KEY" "dr@$FQDN" 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed "s/127.0.0.1/$FQDN/" > "$PRIVATE_DIR/kubeconfig-$NAME"
export KUBECONFIG="$PRIVATE_DIR/kubeconfig-$NAME"
until kubectl wait --for=condition=Ready node --all --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark node_ready
until kubectl -n kube-system rollout status deploy/traefik --timeout=10s >/dev/null 2>&1; do sleep 5; done
mark traefik_ready
