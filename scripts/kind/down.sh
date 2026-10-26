#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
for c in primary standby; do
  kind get clusters 2>/dev/null | grep -qx "$c" && kind delete cluster --name "$c" >/dev/null
done
docker rm -f -v dr-seaweedfs dr-image-copy >/dev/null 2>&1 || true
rm -rf "$STATE_DIR"
log "đã xóa môi trường kind"
