#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
create() {
  az storage account create -n "$1" -g "$2" -l "$3" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
  az storage account keys list -n "$1" -g "$2" --query "[0].value" -o tsv > "$PRIVATE_DIR/key-$1"
}
create "$BACKUP_ACCOUNT" "$RG_JAPAN" "$STORAGE_REGION"
create "$IMAGE_ACCOUNT_PRIMARY" "$RG_PRIMARY" "$CLUSTER_REGION"
create "$IMAGE_ACCOUNT_JAPAN" "$RG_JAPAN" "$STORAGE_REGION"
az storage account blob-service-properties update -n "$IMAGE_ACCOUNT_PRIMARY" -g "$RG_PRIMARY" --enable-versioning true --enable-change-feed true -o none
az storage account blob-service-properties update -n "$IMAGE_ACCOUNT_JAPAN" -g "$RG_JAPAN" --enable-versioning true -o none
for c in cnpg velero; do
  az storage container create -n "$c" --account-name "$BACKUP_ACCOUNT" --account-key "$(cat "$PRIVATE_DIR/key-$BACKUP_ACCOUNT")" -o none
done
az storage container create -n images --account-name "$IMAGE_ACCOUNT_PRIMARY" --account-key "$(cat "$PRIVATE_DIR/key-$IMAGE_ACCOUNT_PRIMARY")" -o none
az storage container create -n images --account-name "$IMAGE_ACCOUNT_JAPAN" --account-key "$(cat "$PRIVATE_DIR/key-$IMAGE_ACCOUNT_JAPAN")" -o none
SOURCE_ID=$(az storage account show -n "$IMAGE_ACCOUNT_PRIMARY" -g "$RG_PRIMARY" --query id -o tsv)
DEST_ID=$(az storage account show -n "$IMAGE_ACCOUNT_JAPAN" -g "$RG_JAPAN" --query id -o tsv)
MSYS_NO_PATHCONV=1 az storage account or-policy create -g "$RG_JAPAN" -n "$IMAGE_ACCOUNT_JAPAN" \
  --source-account "$SOURCE_ID" --destination-account "$DEST_ID" \
  --source-container images --destination-container images -o json > "$PRIVATE_DIR/or-policy.json"
MSYS_NO_PATHCONV=1 az storage account or-policy create -g "$RG_PRIMARY" -n "$IMAGE_ACCOUNT_PRIMARY" --policy "@$(cygpath -m "$PRIVATE_DIR/or-policy.json")" -o none
az storage account or-policy list -g "$RG_PRIMARY" -n "$IMAGE_ACCOUNT_PRIMARY" --query "[].rules[].sourceContainer" -o tsv
