#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

STEPS="detect decide infra restore verify switch"

[ $# -ge 2 ] || die 64 "dùng: step.sh <run_id> --new | step.sh <run_id> <bước> -- <lệnh...>"
run_id="$1"; shift
[[ "$run_id" =~ ^[A-Za-z0-9_-]+$ ]] || die 64 "mã lần diễn tập chỉ gồm chữ, số, - và _"
run_dir="$DATA_DIR/drills/$run_id"

if [ "$1" = "--new" ]; then
  [ ! -e "$run_dir" ] || die 3 "lần diễn tập $run_id đã có ở $run_dir"
  mkdir -p "$run_dir"
  echo "step,started_at,ended_at,result" > "$run_dir/steps.csv"
  exit 0
fi

step="$1"; shift
[[ " $STEPS " == *" $step "* ]] || die 64 "bước phải là một trong: $STEPS"
[ "${1:-}" = "--" ] || die 64 "thiếu -- trước lệnh"
shift
[ $# -ge 1 ] || die 64 "thiếu lệnh"
[ -f "$run_dir/steps.csv" ] || die 3 "chưa tạo lần diễn tập $run_id (chạy step.sh $run_id --new)"

started_at="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
set +e
"$@"
code=$?
set -e
ended_at="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
result=ok
[ "$code" -eq 0 ] || result=fail
echo "$step,$started_at,$ended_at,$result" >> "$run_dir/steps.csv"
exit "$code"
