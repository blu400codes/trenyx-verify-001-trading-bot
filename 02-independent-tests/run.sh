#!/usr/bin/env bash
# Run the independent tests against the target checkout.
#   ./run.sh <target_repo> <venv_python>
set -u
REPO="$1"; PY="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO" && PYTHONPATH="$REPO" "$PY" -m pytest -q -p no:cacheprovider -rA --timeout=300 "$HERE" "${@:3}"
