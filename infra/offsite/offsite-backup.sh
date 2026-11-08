#!/usr/bin/env bash
set -euo pipefail
set -a
source /etc/dr-offsite/env
set +a
cap_bytes=$(( ${OFFSITE_CAP_GIB:-3} * 1024 * 1024 * 1024 ))
cd "$OFFSITE_HOME"
python3 -m scripts.vault.offsite --url "$VAULT_URL" --sas-file /etc/dr-offsite/sas --mirror "$OFFSITE_MIRROR"
restic --retry-lock 10m backup --host quang-service --tag vault "$OFFSITE_MIRROR"
restic --retry-lock 10m forget --keep-daily 7 --prune
size() { restic --retry-lock 10m stats --mode raw-data --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["total_size"])'; }
while [ "$(size)" -gt "$cap_bytes" ]; do
  ids=$(restic --retry-lock 10m snapshots --json | python3 -c 'import json,sys; s=sorted(json.load(sys.stdin), key=lambda x: x["time"]); print(" ".join(x["short_id"] for x in s))')
  set -- $ids
  [ "$#" -gt 1 ] || { echo "kho restic vượt ${OFFSITE_CAP_GIB:-3} GiB dù chỉ còn một bản" >&2; exit 3; }
  restic --retry-lock 10m forget --prune "$1"
done
restic --retry-lock 10m snapshots --compact | tail -n 3
