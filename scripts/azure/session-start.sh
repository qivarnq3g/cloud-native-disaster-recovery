#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"; image_tag="${2:-}"
check_cluster "$cluster"
[ -n "$image_tag" ] || die 64 "cách dùng: session-start.sh <cluster> <image_tag>"

[ "$(vm_count)" -lt 2 ] || die 4 "đã có hai máy vm-dr-*, không dựng máy thứ ba"
state="$(session get state)"
[ "$state" != "running" ] || die 3 "session.json vẫn là running: tắt phiên trước bằng session-stop.sh"
! vm_exists "$cluster" || die 3 "vm-dr-$cluster vẫn còn: tắt phiên trước bằng session-stop.sh"
for s in cluster-up.sh install-software.sh deploy-api.sh; do
  [ -f "$REPO_ROOT/scripts/azure/$s" ] || die 5 "chưa có scripts/azure/$s"
done

old_server="$(session get server_name)"
server_name="$cluster-$(date -u +%Y%m%d%H%M)"
mark session.csv "$cluster" start

bash "$REPO_ROOT/scripts/azure/cluster-up.sh" "$cluster"
ip="$(terraform -chdir="$REPO_ROOT/infra/terraform/cluster" output -raw public_ip)"
mark session.csv "$cluster" vm_ready

bash "$REPO_ROOT/scripts/azure/install-software.sh" "$cluster" "$server_name" "$old_server"
mark session.csv "$cluster" software_ready
bash "$REPO_ROOT/scripts/azure/deploy-api.sh" "$cluster" "$image_tag"
mark session.csv "$cluster" api_ready
dns_switch "$ip" --csv "$DATA_DIR/dns-switch.csv"
mark session.csv "$cluster" dns_switched

session set state=running "cluster=$cluster" "server_name=$server_name" \
  "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" stopped_at= full_backup= velero_backup= post_count= content_digest=
mark session.csv "$cluster" done
echo "phiên $cluster đã chạy, server_name $server_name, IP $ip"
