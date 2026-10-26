#!/usr/bin/env bash
set -euo pipefail

export REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PRIVATE_DIR="${DR_PRIVATE_DIR:-$HOME/.dr}"
export DATA_DIR="${DR_DATA_DIR:-$REPO_ROOT/data/azure}"
export SSH_KEY="$PRIVATE_DIR/ssh_ed25519"
export DR_PYTHON="${DR_PYTHON:-python}"
mkdir -p "$PRIVATE_DIR" "$DATA_DIR"

if [ -n "${DR_SUFFIX:-}" ]; then
  SFX="$DR_SUFFIX"
elif [ -s "$PRIVATE_DIR/suffix" ]; then
  SFX="$(cat "$PRIVATE_DIR/suffix")"
else
  SFX="$("$DR_PYTHON" -c 'import secrets; print(secrets.token_hex(3))')"
  echo "$SFX" > "$PRIVATE_DIR/suffix"
fi
export SFX
[ -f "$SSH_KEY" ] || ssh-keygen -q -t ed25519 -N "" -C "dr-cluster" -f "$SSH_KEY"

export RG_PRIMARY=rg-dr-primary
export RG_STANDBY=rg-dr-standby
export RG_BACKUP=rg-dr-backup
export CLUSTER_REGION=koreacentral
export STORAGE_REGION=japanwest

export STATE_ACCOUNT="drtfstate${SFX}"
export BACKUP_ACCOUNT="drbackup${SFX}"
export IMAGE_COPY_ACCOUNT="drimgcopy${SFX}"
export VAULT_ACCOUNT="drvault${SFX}"
export IMAGE_PRIMARY_ACCOUNT="drimgpri${SFX}"
export IMAGE_STANDBY_ACCOUNT="drimgstb${SFX}"

tf_init() {
  terraform -chdir="$1" init -reconfigure -input=false \
    -backend-config="resource_group_name=$RG_BACKUP" \
    -backend-config="storage_account_name=$STATE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="key=$2"
}
