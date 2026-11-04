#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
email="${DR_BUDGET_EMAIL:-$(cat "$PRIVATE_DIR/budget-email" 2>/dev/null || true)}"
[ -n "$email" ] || die 5 "chưa có email ngân sách: đặt DR_BUDGET_EMAIL hoặc ghi vào $PRIVATE_DIR/budget-email"
! vm_exists standby || die 3 "vm-dr-standby vẫn còn: chạy session-stop.sh standby trước"
if az storage account show -g "$RG_PRIMARY" -n "$IMAGE_PRIMARY_ACCOUNT" --query name -o tsv >/dev/null 2>&1; then
  echo "kho ảnh chính $IMAGE_PRIMARY_ACCOUNT vẫn còn, không cần dựng lại"
  exit 0
fi
[ "$(az group exists -n "$RG_PRIMARY")" = false ] || die 3 "nhóm $RG_PRIMARY đang xóa dở: chờ xóa xong rồi chạy lại"

stack="$REPO_ROOT/infra/terraform/storage"
tf_init "$stack" storage.tfstate >/dev/null
addresses="$(terraform -chdir="$stack" state list)" || die 1 "không đọc được trạng thái stack storage"
while IFS= read -r address; do
  address="${address%$'\r'}"
  case "$address" in
    *'["primary"]'*|*image_primary*|azurerm_storage_object_replication.*)
      terraform -chdir="$stack" state rm "$address" >/dev/null || die 1 "không bỏ được $address khỏi trạng thái" ;;
  esac
done <<< "$addresses"

delete_policies "$RG_BACKUP" "$IMAGE_COPY_ACCOUNT" sourceAccount "$IMAGE_PRIMARY_ACCOUNT"
delete_policies "$RG_STANDBY" "$IMAGE_STANDBY_ACCOUNT" sourceAccount "$IMAGE_PRIMARY_ACCOUNT"
rm -f "$PRIVATE_DIR/key-$IMAGE_PRIMARY_ACCOUNT"

DR_BUDGET_EMAIL="$email" bash "$SCRIPT_DIR/restore-replication.sh"
bash "$SCRIPT_DIR/copy-images.sh" "$IMAGE_STANDBY_ACCOUNT" "$IMAGE_PRIMARY_ACCOUNT"
bash "$SCRIPT_DIR/issue-sas.sh" api-images-primary
echo "đã dựng lại kho ảnh chính $IMAGE_PRIMARY_ACCOUNT; cấp lại check-read bằng issue-sas.sh check-read"
