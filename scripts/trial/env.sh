#!/usr/bin/env bash
set -euo pipefail
export DAY="${DAY:-$(date -u +%m%d)}"
export SUFFIX="${SUFFIX:-$(cat ~/.dr-trial/suffix 2>/dev/null || true)}"
if [ -z "$SUFFIX" ]; then
  SUFFIX="$(python -c 'import secrets; print(secrets.token_hex(3))')"
  echo "$SUFFIX" > ~/.dr-trial/suffix
fi
export RG_PRIMARY=rg-dr-trial-primary
export RG_STANDBY=rg-dr-trial-standby
export RG_JAPAN=rg-dr-trial-japan
export CLUSTER_REGION=koreacentral
export STORAGE_REGION=japanwest
export BACKUP_ACCOUNT="drtrialbk${SUFFIX}"
export IMAGE_ACCOUNT_PRIMARY="drtrialimg${SUFFIX}"
export IMAGE_ACCOUNT_JAPAN="drtrialimgjp${SUFFIX}"
export DNS_PRIMARY="drtrial-primary-${SUFFIX}"
export DNS_STANDBY="drtrial-standby-${SUFFIX}"
export FQDN_PRIMARY="${DNS_PRIMARY}.${CLUSTER_REGION}.cloudapp.azure.com"
export FQDN_STANDBY="${DNS_STANDBY}.${CLUSTER_REGION}.cloudapp.azure.com"
export SSH_KEY=~/.ssh/dr_trial_ed25519
export PRIVATE_DIR=~/.dr-trial
export DATA_DIR="$(git rev-parse --show-toplevel)/data/trial"
export SERVER_PRIMARY="primary-${DAY}"
export SERVER_STANDBY="standby-${DAY}"
