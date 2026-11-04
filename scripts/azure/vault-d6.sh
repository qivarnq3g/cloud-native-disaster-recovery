#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
run_id="${1:-}"
[ -n "$run_id" ] || die 64 "cách dùng: vault-d6.sh <run_id>"
pack="$(session get vault_pack)"
pack="${pack%$'\r'}"
[ -n "$pack" ] || die 5 "session.json chưa có vault_pack: tắt phiên một lần để job két tạo gói"
writer_sas="$(cat "$PRIVATE_DIR/sas-vault-writer.txt" 2>/dev/null)"
[ -n "$writer_sas" ] || die 5 "chưa có sas-vault-writer.txt: chạy issue-sas.sh vault-writer"
expiry="$(date -u -d '+1 hour' +%Y-%m-%dT%H:%MZ)"
key_sas="$(az storage account generate-sas --account-name "$VAULT_ACCOUNT" --account-key "$(account_key "$VAULT_ACCOUNT")" \
  --services b --resource-types sco --permissions racwdl --expiry "$expiry" --https-only -o tsv)"
[ -n "$key_sas" ] || die 1 "không ký được SAS bằng khóa tài khoản $VAULT_ACCOUNT"

out_dir="$DATA_DIR/drills/$run_id"
mkdir -p "$out_dir"
csv="$out_dir/vault-d6.csv"
echo "attempt,actor,expected,outcome,http_status,error_code" > "$csv"
url="https://$VAULT_ACCOUNT.blob.core.windows.net/vault/$pack"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
printf 'd6' > "$work/body"
broken=0

attempt() {
  local name="$1" actor="$2" method="$3" sas="$4" status code outcome
  local args=(-s -o "$work/resp" -D "$work/headers" -w '%{http_code}' -X "$method" -H "x-ms-version: 2023-11-03")
  [ "$method" = PUT ] && args+=(-H "x-ms-blob-type: BlockBlob" --data-binary "@$work/body")
  : > "$work/headers"
  status="$(curl "${args[@]}" "$url?${sas#\?}")"
  code="$(sed -n 's/^x-ms-error-code: *//Ip' "$work/headers" | tr -d '\r')"
  case "$status" in 2??) outcome=allowed; broken=1 ;; *) outcome=refused ;; esac
  echo "$name,$actor,refused,$outcome,$status,$code" >> "$csv"
  echo "$name ($actor): $outcome, HTTP $status $code"
}

attempt delete account-key DELETE "$key_sas"
attempt overwrite account-key PUT "$key_sas"
attempt delete vault-writer DELETE "$writer_sas"
attempt overwrite vault-writer PUT "$writer_sas"

policy=(--account-name "$VAULT_ACCOUNT" -g "$RG_BACKUP" -c vault)
etag="$(az storage container immutability-policy show "${policy[@]}" --query etag -o tsv)"
if az storage container immutability-policy create "${policy[@]}" --period 1 --if-match "$etag" -o none 2> "$work/err"; then
  echo "shorten-policy,account-key,refused-after-lock,allowed,," >> "$csv"
  echo "rút ngắn WORM xuống 1 ngày: được (chính sách chưa khóa cứng), đặt lại 7 ngày"
  etag="$(az storage container immutability-policy show "${policy[@]}" --query etag -o tsv)"
  az storage container immutability-policy create "${policy[@]}" --period 7 --if-match "$etag" -o none \
    || die 1 "không đặt lại được WORM 7 ngày cho $VAULT_ACCOUNT/vault: sửa tay ngay"
else
  code="$(grep -o '[A-Za-z]*Immutab[A-Za-z]*\|[A-Za-z]*Locked[A-Za-z]*' "$work/err" | head -1)"
  echo "shorten-policy,account-key,refused-after-lock,refused,,$code" >> "$csv"
  echo "rút ngắn WORM: bị từ chối $code"
fi

[ "$broken" = 0 ] || die 1 "D6 không đạt: có cách xóa hoặc ghi đè gói $pack, xem $csv"
echo "D6 đạt: bốn cách xóa và ghi đè đều bị từ chối, biên bản $csv"
