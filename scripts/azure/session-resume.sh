#!/usr/bin/env bash
# session-resume.sh <cluster>: bật lại máy đã nghỉ, chờ /healthz trên IP của máy trả 200.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"
name="${DR_API_NAME:-api.dr.qivarn.id.vn}"
az vm start -g "rg-dr-$cluster" -n "vm-dr-$cluster"
ip="$(az vm show -d -g "rg-dr-$cluster" -n "vm-dr-$cluster" --query publicIps -o tsv)"
deadline=$((SECONDS + 600))
until curl -fsS -o /dev/null --resolve "$name:443:$ip" "https://$name/healthz"; do
  [ "$SECONDS" -lt "$deadline" ] || die 1 "sau 10 phút https://$name/healthz trên $ip vẫn chưa trả 200"
  sleep "${DR_POLL_SECONDS:-5}"
done
mark session.csv "$cluster" resumed
echo "vm-dr-$cluster chạy lại, /healthz trả 200"
