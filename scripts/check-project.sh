#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python >/dev/null 2>&1; then
  python_cmd="python"
elif command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
else
  echo "python or python3 is required"
  exit 1
fi

"${python_cmd}" "${repo_root}/scripts/test_agent/run.py"
