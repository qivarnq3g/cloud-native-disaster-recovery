#!/usr/bin/env bash
set -uo pipefail
name="$1"
show() { printf '\n\033[1;32m$\033[0m %s\n' "$1"; sleep 1; bash -c "$1"; local s=$?; sleep 2; return "$s"; }
status=0
case "$name" in
  normal)
    show "kubectl --context kind-primary get pods -n dr-api" || status=$?
    show "curl -s http://127.0.0.1:18080/healthz; echo" || status=$?
    show "curl -s 'http://127.0.0.1:18080/v1/posts?limit=2' | python3 -m json.tool | head -24" || status=$?
    show "kubectl --context kind-primary get scheduledbackups.postgresql.cnpg.io,backups.postgresql.cnpg.io -n dr-api" || status=$?
    show "kubectl --context kind-primary get schedules.velero.io,backups.velero.io -n velero" || status=$?
    show "kubectl --context kind-standby get pods -n dr-api" || status=$?
    ;;
  *)
    show "scripts/kind/run.sh $name" || status=$?
    ;;
esac
echo "$status" > "$DEMO_DIR/$name.status"
