#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
src="$IMAGE_COPY_ACCOUNT"; dst="$IMAGE_STANDBY_ACCOUNT"
dst_key="$(account_key "$dst")"
started=$(date +%s)

az storage blob copy start-batch --account-name "$dst" --account-key "$dst_key" --destination-container images \
  --source-account-name "$src" --source-account-key "$(account_key "$src")" --source-container images -o none \
  || die 1 "không bắt đầu chép được ảnh từ $src"
until [ "$(az storage blob list --account-name "$dst" --account-key "$dst_key" -c images --include c --num-results '*' \
    --query "length([?properties.copy.status!='success'])" -o tsv)" = 0 ]; do
  sleep "${DR_POLL_SECONDS:-5}"
done
count="$(az storage blob list --account-name "$dst" --account-key "$dst_key" -c images --num-results '*' --query "length(@)" -o tsv)"
echo "đã chép $count ảnh từ $src sang $dst trong $(( $(date +%s) - started )) s"
