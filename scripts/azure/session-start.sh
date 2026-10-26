#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"; image_tag="${2:-}"
check_cluster "$cluster"
[ -n "$image_tag" ] || die 64 "cách dùng: session-start.sh <cluster> <image_tag>"

[ "$(vm_count)" -lt 2 ] || die 4 "đã có hai máy vm-dr-*, không dựng máy thứ ba"
state="$(session get state)"
[ "$state" != "running" ] || die 3 "session.json vẫn là running: tắt phiên trước bằng session-stop.sh"
! vm_exists "$cluster" || die 3 "vm-dr-$cluster vẫn còn: tắt phiên trước bằng session-stop.sh"
for s in install-software.sh deploy-api.sh; do
  [ -f "$REPO_ROOT/scripts/azure/$s" ] || die 5 "chưa có scripts/azure/$s"
done

old_server="$(session get server_name)"
server_name="$cluster-$(date -u +%Y%m%d%H%M)"
mark session.csv "$cluster" start

stack="$REPO_ROOT/infra/terraform/cluster"
tf_init "$stack" "cluster-$cluster.tfstate"
terraform -chdir="$stack" apply -auto-approve -input=false \
  -var "cluster=$cluster" -var "suffix=$SFX" \
  -var "admin_cidrs=[\"${ADMIN_IP:-$(curl -fsS https://api.ipify.org)}/32\"]" \
  -var "ssh_public_key=$(cat "$SSH_KEY.pub")"
ip="$(terraform -chdir="$stack" output -raw public_ip)"
mark session.csv "$cluster" vm_ready

bash "$REPO_ROOT/scripts/azure/install-software.sh" "$cluster" "$server_name" "$old_server"
mark session.csv "$cluster" software_ready
bash "$REPO_ROOT/scripts/azure/deploy-api.sh" "$cluster" "$image_tag"
mark session.csv "$cluster" api_ready
(cd "$REPO_ROOT" && "$DR_PYTHON" -m scripts.dr.dns_switch "$ip" --csv "$DATA_DIR/dns-switch.csv")
mark session.csv "$cluster" dns_switched

session set state=running "cluster=$cluster" "server_name=$server_name" \
  "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" stopped_at= full_backup= velero_backup= post_count= content_digest=
mark session.csv "$cluster" done
echo "phiên $cluster đã chạy, server_name $server_name, IP $ip"
