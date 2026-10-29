#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../../scripts/azure/env.sh"

providers=(Microsoft.Storage Microsoft.Compute Microsoft.Network Microsoft.Insights Microsoft.Consumption Microsoft.DevTestLab)
for p in "${providers[@]}"; do
  state="$(az provider show -n "$p" --query registrationState -o tsv)"
  if [ "$state" != "Registered" ]; then
    echo "registering $p ($state)"
    az provider register -n "$p" --wait
  fi
done

if [ "$(az group exists -n "$RG_BACKUP")" != "true" ]; then
  az group create -n "$RG_BACKUP" -l "$STORAGE_REGION" -o none
fi

if ! az storage account show -g "$RG_BACKUP" -n "$STATE_ACCOUNT" -o none 2>/dev/null; then
  az storage account create -g "$RG_BACKUP" -n "$STATE_ACCOUNT" -l "$STORAGE_REGION" \
    --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
    --allow-blob-public-access false -o none
fi
az storage account blob-service-properties update -g "$RG_BACKUP" -n "$STATE_ACCOUNT" \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 7 -o none

key="$(az storage account keys list -g "$RG_BACKUP" -n "$STATE_ACCOUNT" --query "[0].value" -o tsv)"
if [ "$(az storage container exists --account-name "$STATE_ACCOUNT" --account-key "$key" -n tfstate --query exists -o tsv)" != "true" ]; then
  az storage container create --account-name "$STATE_ACCOUNT" --account-key "$key" -n tfstate -o none
fi

if ! az lock show -g "$RG_BACKUP" -n protect-state --resource-type Microsoft.Storage/storageAccounts --resource "$STATE_ACCOUNT" -o none 2>/dev/null; then
  az lock create -g "$RG_BACKUP" -n protect-state --lock-type CanNotDelete \
    --resource-type Microsoft.Storage/storageAccounts --resource "$STATE_ACCOUNT" -o none
fi

echo "bootstrap ok: $STATE_ACCOUNT"
