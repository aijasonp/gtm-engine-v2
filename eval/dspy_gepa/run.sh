#!/usr/bin/env bash
# Convenience wrapper for the DSPy+GEPA prompt optimization layer.
# Sources ~/.openclaw/.env for COMPANY_API_KEY, runs the optimizer with the venv
# python, and prints a summary of optimized scores.
set -euo pipefail

cd "$(dirname "$0")/.."   # gtm-agent-eval/

# Source COMPANY_API_KEY (and any other env vars) from ~/.openclaw/.env
if [ -f "$HOME/.openclaw/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.openclaw/.env"
  set +a
fi

if [ -z "${COMPANY_API_KEY:-}" ]; then
  echo "ERROR: COMPANY_API_KEY not set. Check ~/.openclaw/.env" >&2
  exit 1
fi

VENV_PY=".venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: venv python not found at $VENV_PY" >&2
  exit 1
fi

echo "Running DSPy+GEPA optimizer (venv: $VENV_PY)..."
"$VENV_PY" dspy_gepa/optimizer.py

echo
echo "Optimized programs saved to dspy_gepa/optimized/"
