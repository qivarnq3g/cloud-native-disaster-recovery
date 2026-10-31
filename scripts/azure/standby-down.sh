#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if [ "$(session get state)" = "running" ] && [ "$(session get cluster)" = "standby" ]; then
  die 3 "cụm dự phòng đang là cụm chính của phiên: tắt bằng session-stop.sh standby"
fi
mark standby.csv standby down_start
if vm_exists standby; then refresh_admin_ip standby; fi

stack="$REPO_ROOT/infra/terraform/cluster"
tf_init "$stack" "cluster-standby.tfstate" >/dev/null
terraform -chdir="$stack" destroy -auto-approve -input=false \
  -var "cluster=standby" -var "suffix=$SFX" -var 'admin_cidrs=["0.0.0.0/32"]' \
  -var "ssh_public_key=$(cat "$SSH_KEY.pub")"
left="$(az vm list -g rg-dr-standby --query "length(@)" -o tsv)"
[ "$left" = "0" ] || die 1 "rg-dr-standby vẫn còn $left máy"
rm -f "$PRIVATE_DIR/standby-server" "$PRIVATE_DIR/kubeconfig-standby"
mark standby.csv standby down_done
echo "đã xóa cụm dự phòng ấm"
