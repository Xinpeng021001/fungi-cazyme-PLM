#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  met_run.sh [--name NAME] [--gpu GPU_IDS] [--allow-dirty] -- COMMAND [ARG ...]

Examples:
  met_run.sh --name smoke --gpu 0 -- .venv/bin/python -m pytest
  met_run.sh --name phase0 --gpu 0,1 -- make phase0

The script creates an immutable logs/remote_runs/<run_id>/ directory containing
run.json, environment.txt, stdout.log, and stderr.log. Run it inside tmux for
long jobs. A dirty Git worktree is rejected unless --allow-dirty is explicit.
EOF
}

run_name="remote"
gpu_ids=""
allow_dirty=0

while (($#)); do
  case "$1" in
    --name)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      run_name="$2"
      shift 2
      ;;
    --gpu)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      gpu_ids="$2"
      shift 2
      ;;
    --allow-dirty)
      allow_dirty=1
      shift
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "met_run.sh: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if (($# == 0)); then
  echo "met_run.sh: COMMAND is required after --" >&2
  usage >&2
  exit 2
fi

command_args=("$@")
project_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "met_run.sh: run inside the fungi-cazyme-PLM Git repository" >&2
  exit 2
}
cd "$project_root"

git_commit="$(git rev-parse HEAD)"
git_dirty=false
if [[ -n "$(git status --porcelain)" ]]; then
  git_dirty=true
  if ((allow_dirty == 0)); then
    echo "met_run.sh: refusing a dirty Git worktree; commit/stash changes or pass --allow-dirty" >&2
    exit 2
  fi
fi

safe_name="$(printf '%s' "$run_name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9._-' '-' | sed 's/^-//;s/-$//')"
[[ -n "$safe_name" ]] || safe_name="remote"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_id="${timestamp}_${git_commit:0:8}_${safe_name}"
log_dir="$project_root/logs/remote_runs/$run_id"
mkdir -p "$log_dir"
manifest="$log_dir/run.json"
stdout_log="$log_dir/stdout.log"
stderr_log="$log_dir/stderr.log"

write_manifest() {
  local status="$1"
  local ended_at="$2"
  local exit_code="$3"
  python3 -c '
import json
import pathlib
import shlex
import socket
import sys

(
    path, run_id, status, started_at, ended_at, exit_code, project_root,
    git_commit, git_dirty, gpu_ids, log_dir, *command
) = sys.argv[1:]
payload = {
    "run_id": run_id,
    "status": status,
    "started_at_utc": started_at,
    "ended_at_utc": ended_at or None,
    "exit_code": int(exit_code) if exit_code else None,
    "hostname": socket.gethostname(),
    "project_root": project_root,
    "git_commit": git_commit,
    "git_dirty": git_dirty == "true",
    "cuda_visible_devices": gpu_ids or None,
    "command": command,
    "command_text": shlex.join(command),
    "log_dir": log_dir,
}
target = pathlib.Path(path)
temporary = target.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(target)
' "$manifest" "$run_id" "$status" "$started_at" "$ended_at" "$exit_code" \
    "$project_root" "$git_commit" "$git_dirty" "$gpu_ids" "$log_dir" \
    "${command_args[@]}"
}

write_manifest running "" ""

{
  printf 'run_id\t%s\n' "$run_id"
  printf 'started_at_utc\t%s\n' "$started_at"
  printf 'hostname\t%s\n' "$(hostname)"
  printf 'project_root\t%s\n' "$project_root"
  printf 'git_commit\t%s\n' "$git_commit"
  printf 'git_dirty\t%s\n' "$git_dirty"
  printf 'cuda_visible_devices\t%s\n' "${gpu_ids:-unset}"
  printf 'uname\t%s\n' "$(uname -a)"
  printf 'python3\t%s\n' "$(python3 --version 2>&1)"
  printf 'uv\t%s\n' "$(uv --version 2>/dev/null || echo unavailable)"
  printf 'disk_array1\t%s\n' "$(df -h /array1 2>/dev/null | tail -n 1 || echo unavailable)"
  printf '\n[gpus]\n'
  nvidia-smi --query-gpu=index,name,memory.total,driver_version \
    --format=csv,noheader 2>/dev/null || echo unavailable
  printf '\n[git-status]\n'
  git status --short --branch
  if [[ -x .venv/bin/python ]]; then
    printf '\n[venv-python]\n'
    .venv/bin/python --version
    printf '\n[venv-packages]\n'
    .venv/bin/python -m pip freeze 2>/dev/null || true
  fi
} > "$log_dir/environment.txt"

finish() {
  local exit_code=$?
  local ended_at
  local status
  ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if ((exit_code == 0)); then
    status="completed"
  else
    status="failed"
  fi
  write_manifest "$status" "$ended_at" "$exit_code"
  printf '\n[fcplm-remote] run_id=%s status=%s exit_code=%s\n' \
    "$run_id" "$status" "$exit_code" >&2
  printf '[fcplm-remote] logs=%s\n' "$log_dir" >&2
}
trap finish EXIT

printf '[fcplm-remote] run_id=%s\n' "$run_id"
printf '[fcplm-remote] commit=%s dirty=%s gpu=%s\n' \
  "$git_commit" "$git_dirty" "${gpu_ids:-unset}"
printf '[fcplm-remote] command='
printf '%q ' "${command_args[@]}"
printf '\n'

if [[ -n "$gpu_ids" ]]; then
  CUDA_VISIBLE_DEVICES="$gpu_ids" "${command_args[@]}" \
    > >(tee "$stdout_log") 2> >(tee "$stderr_log" >&2)
else
  "${command_args[@]}" \
    > >(tee "$stdout_log") 2> >(tee "$stderr_log" >&2)
fi

