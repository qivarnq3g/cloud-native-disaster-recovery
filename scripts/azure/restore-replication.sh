#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
email="${DR_BUDGET_EMAIL:-$(cat "$PRIVATE_DIR/budget-email" 2>/dev/null || true)}"
[ -n "$email" ] || die 5 "chưa có email ngân sách: đặt DR_BUDGET_EMAIL hoặc ghi vào $PRIVATE_DIR/budget-email"

if az storage account or-policy list -g "$RG_PRIMARY" --account-name "$IMAGE_PRIMARY_ACCOUNT" --query "[].policyId" -o tsv \
    >/dev/null 2>&1; then
  delete_standby_policies "$RG_PRIMARY" "$IMAGE_PRIMARY_ACCOUNT"
fi

stack="$REPO_ROOT/infra/terraform/storage"
tf_init "$stack" storage.tfstate >/dev/null
terraform -chdir="$stack" apply -auto-approve -input=false -var "suffix=$SFX" -var "budget_email=$email" \
  || die 1 "áp dụng stack storage lỗi"
echo "đã dựng lại chính sách chép ảnh từ kho chính"
