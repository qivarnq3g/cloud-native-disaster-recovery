#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
server_file="$PRIVATE_DIR/failover-server"

case "${1:-}" in
  --infra)
    vm_exists "$2" || bash "$SCRIPT_DIR/cluster-up.sh" "$2"
    exit 0 ;;
  --restore)
    cluster="$2"
    source_server="$(session get server_name)"
    [ -n "$source_server" ] || die 5 "session.json chưa có server_name để khôi phục"
    server="$cluster-$(date -u +%Y%m%d%H%M)"
    copy_pid=
    if [ "${DR_IMAGES_FROM_COPY:-false}" = true ]; then
      bash "$REPO_ROOT/scripts/azure/copy-images.sh" & copy_pid=$!
    fi
    if ! { bash "$SCRIPT_DIR/install-software.sh" "$cluster" "$server" "$source_server" \
        && bash "$SCRIPT_DIR/deploy-api.sh" "$cluster" "${DR_IMAGE_TAG:-main}"; }; then
      [ -z "$copy_pid" ] || kill "$copy_pid" 2>/dev/null || true
      die 1 "khôi phục trên $cluster lỗi"
    fi
    [ -z "$copy_pid" ] || wait "$copy_pid" || die 1 "chép ảnh sang kho dự phòng lỗi"
    [ "$cluster" != standby ] || remove_image_replication
    echo "$server" > "$server_file"
    exit 0 ;;
  --switch)
    switch_to "$2" "$(cat "$server_file")"
    rm -f "$server_file"
    exit 0 ;;
esac

run_id="${1:-}"; cluster="${2:-}"
check_cluster "$cluster"
run_step "$run_id" infra bash "$0" --infra "$cluster"
run_step "$run_id" restore bash "$0" --restore "$cluster"
run_step "$run_id" switch bash "$0" --switch "$cluster"
echo "đã khôi phục lạnh sang $cluster"
