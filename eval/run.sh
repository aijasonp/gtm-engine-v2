#!/usr/bin/env bash
# GTM agent monthly evaluation runner wrapper.
# Usage: ./run.sh [--month YYYY-MM] [--per-category N] [--judge MODEL]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating venv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet deepeval ragas
fi

exec "$VENV/bin/python" "$DIR/monthly_eval/run.py" "$@"
