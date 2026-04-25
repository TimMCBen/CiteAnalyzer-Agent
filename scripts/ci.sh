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

"${repo_root}/scripts/check-docs.sh"
"${repo_root}/scripts/check-repo-hygiene.sh"
"${repo_root}/scripts/check-action-pinning.sh"
"${python_cmd}" "${repo_root}/scripts/test_agent/run.py"

while IFS= read -r file; do
  bash -n "$file"
done < <(find "${repo_root}/scripts" -type f -name '*.sh' | sort)

if [[ -f "${repo_root}/scripts/check-project.sh" ]]; then
  bash "${repo_root}/scripts/check-project.sh"
fi

echo "基础 CI 检查通过"
