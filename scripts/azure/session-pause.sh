#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cluster="${1:-}"
check_cluster "$cluster"
az vm deallocate -g "rg-dr-$cluster" -n "vm-dr-$cluster"
state="$(power_state "$cluster")"
[ "$state" = "PowerState/deallocated" ] || die 1 "vm-dr-$cluster đang $state, chưa deallocated"
mark session.csv "$cluster" paused
echo "vm-dr-$cluster đã deallocated"
