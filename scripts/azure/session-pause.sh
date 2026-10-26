#!/usr/bin/env bash
# session-pause.sh <cluster>: tắt hẳn máy (deallocate, không còn tính tiền máy). Không đổi session.json.
# Lúc nghỉ không có WAL mới, nên backup-check sẽ báo WAL cũ: chỉ nghỉ dưới 1 giờ, lâu hơn thì session-stop.sh.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"
az vm deallocate -g "rg-dr-$cluster" -n "vm-dr-$cluster"
state="$(power_state "$cluster")"
# "stopped" vẫn tính tiền máy, chỉ "deallocated" mới thôi.
[ "$state" = "PowerState/deallocated" ] || die 1 "vm-dr-$cluster đang $state, chưa deallocated"
mark session.csv "$cluster" paused
echo "vm-dr-$cluster đã deallocated"
