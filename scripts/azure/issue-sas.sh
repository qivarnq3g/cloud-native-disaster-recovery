#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
name="${1:-}"
days="${DR_SAS_DAYS:-30}"
expiry="$(date -u -d "+$days days" +%Y-%m-%dT%H:%MZ)"

case "$name" in
  api-images-primary) targets=("$IMAGE_PRIMARY_ACCOUNT/images"); perms=racwl; secret= ;;
  api-images-standby) targets=("$IMAGE_STANDBY_ACCOUNT/images"); perms=racwl; secret= ;;
  cnpg-backup) targets=("$BACKUP_ACCOUNT/cnpg"); perms=racwdl; secret= ;;
  check-read)
    targets=("$BACKUP_ACCOUNT/cnpg" "$BACKUP_ACCOUNT/velero" "$BACKUP_ACCOUNT/status"
             "$IMAGE_PRIMARY_ACCOUNT/images" "$IMAGE_COPY_ACCOUNT/images")
    perms=rl; secret=BACKUP_CHECK_SAS_JSON ;;
  drill-read)
    targets=("$BACKUP_ACCOUNT/cnpg" "$BACKUP_ACCOUNT/velero" "$BACKUP_ACCOUNT/status"
             "$IMAGE_COPY_ACCOUNT/images")
    perms=rl; secret=DRILL_READ_SAS_JSON ;;
  *) die 64 "cách dùng: issue-sas.sh api-images-primary|api-images-standby|cnpg-backup|check-read|drill-read" ;;
esac

account_key() {
  local account="$1" file="$PRIVATE_DIR/key-$1" group
  if [ ! -s "$file" ]; then
    case "$account" in
      "$IMAGE_PRIMARY_ACCOUNT") group="$RG_PRIMARY" ;;
      "$IMAGE_STANDBY_ACCOUNT") group="$RG_STANDBY" ;;
      *) group="$RG_BACKUP" ;;
    esac
    az storage account keys list -g "$group" -n "$account" --query "[0].value" -o tsv > "$file"
    chmod 600 "$file"
  fi
  cat "$file"
}

json="{"
first=1
for t in "${targets[@]}"; do
  account="${t%%/*}"; container="${t#*/}"
  sas="$(az storage container generate-sas --account-name "$account" --account-key "$(account_key "$account")" \
    -n "$container" --permissions "$perms" --expiry "$expiry" --https-only -o tsv)"
  [ -n "$sas" ] || die 1 "không cấp được SAS cho $t"
  [ "$first" = 1 ] || json+=","
  json+="\"https://$account.blob.core.windows.net/$container\":\"$sas\""
  first=0
  single="$sas"
done
json+="}"

out="$PRIVATE_DIR/sas-$name.txt"
if [ "${#targets[@]}" -eq 1 ]; then printf '%s' "$single" > "$out"; else printf '%s' "$json" > "$out"; fi
chmod 600 "$out"
session sas-expiry "$name" "$expiry"
if [ -n "$secret" ]; then
  gh secret set "$secret" --repo "${DR_REPO:-qivarnq3g/cloud-native-disaster-recovery}" < "$out"
fi
echo "đã cấp $name, hết hạn $expiry"
