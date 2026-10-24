#!/usr/bin/env bash
# GTM agent Promptfoo golden-input regression suite runner.
#
# Runs `promptfoo eval` against the golden prompts and exits non-zero if any
# test fails (regression). Not wired to cron yet; run manually or from CI.
#
# Usage:  ./run.sh [--view] [--max-concurrency N]
set -euo pipefail

cd "$(dirname "$0")"

# Load COMPANY_API_KEY from the OpenClaw env file if not already set.
if [[ -z "${COMPANY_API_KEY:-}" && -f "$HOME/.openclaw/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.openclaw/.env"
  set +a
fi

if [[ -z "${COMPANY_API_KEY:-}" ]]; then
  echo "ERROR: COMPANY_API_KEY is not set. Export it or add it to ~/.openclaw/.env" >&2
  exit 1
fi

VIEW=0
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --view) VIEW=1 ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

echo "==> Running the GTM agent golden-input regression suite (promptfoo eval) ..."
# --no-progress-bar keeps output clean for CI/log capture.
npx promptfoo eval --no-progress-bar "${EXTRA_ARGS[@]}"

status=$?
if [[ $status -ne 0 ]]; then
  echo "==> FAIL: promptfoo eval exited with status $status (regression detected)." >&2
  exit $status
fi

echo "==> PASS: all golden tests passed."
if [[ $VIEW -eq 1 ]]; then
  npx promptfoo view
fi
exit 0
