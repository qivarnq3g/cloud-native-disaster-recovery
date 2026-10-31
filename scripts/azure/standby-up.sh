#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
image_tag="${1:-}"
[ -n "$image_tag" ] || die 64 "cách dùng: standby-up.sh <image_tag>"

[ "$(session get state)" = "running" ] || die 5 "cụm chính chưa chạy: bật phiên bằng session-start.sh trước"
! vm_exists standby || die 3 "vm-dr-standby đã có: xóa bằng standby-down.sh trước"
[ "$(vm_count)" -lt 2 ] || die 4 "đã có hai máy vm-dr-*, không dựng máy thứ ba"

source_server="$(session get server_name)"
[ -n "$source_server" ] || die 5 "session.json chưa có server_name của cụm chính"
server_name="standby-$(date -u +%Y%m%d%H%M)"
mark standby.csv standby start

refresh_admin_ip primary
KUBECONFIG="$PRIVATE_DIR/kubeconfig-primary" take_full_backup "seed-$(date -u +%Y%m%d%H%M)" >/dev/null || exit 1
mark standby.csv standby seed_backup_done

bash "$SCRIPT_DIR/cluster-up.sh" standby
mark standby.csv standby vm_ready
DR_DB_MODE=replica bash "$SCRIPT_DIR/install-software.sh" standby "$server_name" "$source_server"
echo "$server_name" > "$PRIVATE_DIR/standby-server"
mark standby.csv standby replica_ready
DR_READ_ONLY=true bash "$SCRIPT_DIR/deploy-api.sh" standby "$image_tag"
mark standby.csv standby api_ready
echo "cụm dự phòng ấm đã chạy, server_name $server_name, đọc WAL của $source_server"
