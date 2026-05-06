#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_script="${repo_root}/scripts/test_agent/run.py"

if command -v python.exe >/dev/null 2>&1 && python.exe -c "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)" >/dev/null 2>&1; then
  python_cmd="python.exe"
elif command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)" >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "python3 is required, or python must point to Python 3"
  exit 1
fi

if [ "${python_cmd}" = "python.exe" ]; then
  if command -v wslpath >/dev/null 2>&1; then
    run_script="$(wslpath -w "$run_script")"
  elif command -v cygpath >/dev/null 2>&1; then
    run_script="$(cygpath -w "$run_script")"
  fi
fi

"${python_cmd}" "${run_script}"
