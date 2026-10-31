#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

scenario="${1:-}"
case "$scenario" in
  D1|D2|D3|D4|D5) ;;
  *) die 64 "dùng: break.sh <D1|D2|D3|D4|D5>" ;;
esac

[ "$scenario" != D1 ] || refresh_admin_ip primary
echo "phá $scenario lúc $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
case "$scenario" in
  D1)
    export KUBECONFIG="$PRIVATE_DIR/kubeconfig-primary"
    kubectl delete namespace dr-api --wait=false || die 1 "không xóa được namespace dr-api" ;;
  D2|D3)
    az vm delete -g "$RG_PRIMARY" -n vm-dr-primary --yes --force-deletion true --no-wait \
      || die 1 "không xóa được vm-dr-primary" ;;
  D4|D5)
    az group delete -n "$RG_PRIMARY" --yes --no-wait || die 1 "không xóa được nhóm $RG_PRIMARY" ;;
esac
