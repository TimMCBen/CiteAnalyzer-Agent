"""Command-line validation helpers for import contract."""
from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import StageLogger


def assert_stage1_import_path_does_not_require_bs4() -> None:
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "bs4" or name.startswith("bs4."):
            raise ModuleNotFoundError("No module named 'bs4'")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded_import
    try:
        sys.modules.pop("apps.analyzer.nodes", None)
        module = importlib.import_module("apps.analyzer.nodes")
    finally:
        builtins.__import__ = original_import

    assert hasattr(module, "parse_user_query")
    assert hasattr(module, "resolve_target_paper_node")


def main() -> None:
    """Run this module as a command-line validation or utility entry point."""
    logger = StageLogger("import_contract")
    logger.start()
    logger.detail("guarded_optional_dependency=bs4 import_target=apps.analyzer.nodes symbols=parse_user_query,resolve_target_paper_node")
    assert_stage1_import_path_does_not_require_bs4()
    logger.pass_case(
        "stage1_import_without_bs4",
        detail="module=apps.analyzer.nodes symbols=parse_user_query,resolve_target_paper_node",
    )
    logger.done("import contract validation passed")


if __name__ == "__main__":
    main()
