"""Validate purpose-oriented module, class, and function docstring coverage."""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import StageLogger

EXCLUDED_PARTS = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "downloaded-papers",
    "external",
    "generated-reports",
    "logs",
    "Thesis_Crawling_and_Filtering_System",
}

SCOPE_ROOTS = {
    "core": [
        "packages/shared",
        "apps/analyzer",
        "packages/citation_sources",
    ],
    "analysis": [
        "packages/author_intel",
        "packages/paper_identity",
        "packages/sentiment",
    ],
    "reporting-eval": [
        "packages/reporting",
        "scripts/eval",
    ],
    "tests": [
        "scripts/test_agent",
    ],
}

ACCESSOR_NAMES = {
    "to_dict",
    "to_log_dict",
    "as_dict",
    "dict",
    "JSON",
}

ORDINARY_DUNDER_NAMES = {
    "__enter__",
    "__exit__",
    "__iter__",
    "__len__",
    "__repr__",
    "__str__",
}

BANNED_DOCSTRING_MARKERS = (
    "behavior for",
    "project automation",
    "returns the result",
    "support ",
    " responsibilities",
    "this function calls",
    " l l m ",
)


@dataclass(frozen=True)
class Finding:
    """Describe one required, missing, exempt, or skipped docstring target."""

    path: str
    kind: str
    name: str
    line: int
    status: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for reports."""
        return {
            "path": self.path,
            "kind": self.kind,
            "name": self.name,
            "line": self.line,
            "status": self.status,
            "reason": self.reason,
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for scoped docstring contract checks."""
    parser = argparse.ArgumentParser(description="Validate purpose docstring coverage.")
    parser.add_argument("--scope", choices=sorted(SCOPE_ROOTS), default=None, help="Limit validation to one rollout scope.")
    parser.add_argument("--path", action="append", default=[], help="Additional file or directory path to validate.")
    parser.add_argument("--report-only", action="store_true", help="Print missing items without failing.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the docstring coverage contract as a standalone validation script."""
    args = parse_args(argv)
    logger = StageLogger("comment_contract")
    logger.start()
    findings = collect_findings(resolve_paths(args))
    summary = summarize(findings)

    if args.json:
        print(json.dumps({"summary": summary, "findings": [item.as_dict() for item in findings]}, ensure_ascii=False, indent=2))
    else:
        logger.detail(
            " ".join(
                f"{key}={value}"
                for key, value in summary.items()
            )
        )
        for item in [finding for finding in findings if finding.status == "missing"][:40]:
            print(f"MISSING {item.path}:{item.line} {item.kind} {item.name} reason={item.reason}")
        if summary["missing"] > 40:
            print(f"... {summary['missing'] - 40} more missing docstrings")

    if summary["missing"] and not args.report_only:
        logger.fail("docstring coverage", detail=f"missing={summary['missing']}")
        raise SystemExit(1)

    logger.pass_case("docstring_coverage", detail=" ".join(f"{key}={value}" for key, value in summary.items()))
    logger.done("comment contract validation passed")


def resolve_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve configured scope and explicit path arguments into scan roots."""
    if args.path:
        return [resolve_repo_path(value) for value in args.path]
    if args.scope:
        return [resolve_repo_path(value) for value in SCOPE_ROOTS[args.scope]]
    return [REPO_ROOT / "apps", REPO_ROOT / "packages", REPO_ROOT / "scripts"]


def resolve_repo_path(value: str) -> Path:
    """Resolve a repository-relative or absolute path."""
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def iter_python_files(paths: Iterable[Path]) -> list[Path]:
    """Collect Python files under scan roots while excluding generated areas."""
    files: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*.py")
        for candidate in candidates:
            if candidate.suffix != ".py":
                continue
            if any(part in EXCLUDED_PARTS for part in candidate.relative_to(REPO_ROOT).parts):
                continue
            files.append(candidate)
    return sorted(set(files))


def collect_findings(paths: Iterable[Path]) -> list[Finding]:
    """Collect required, missing, and exempt docstring findings for paths."""
    findings: list[Finding] = []
    for path in iter_python_files(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        findings.append(module_finding(path, rel_path, tree))
        for node, parent in iter_symbol_nodes(tree):
            findings.append(symbol_finding(rel_path, node, parent))
    return findings


def module_finding(path: Path, rel_path: str, tree: ast.Module) -> Finding:
    """Classify module-level docstring coverage for one file."""
    has_docstring = bool(ast.get_docstring(tree))
    if path.name == "__init__.py" and not tree.body:
        return Finding(rel_path, "module", rel_path, 1, "exempt", "empty_init")
    if has_docstring and has_low_quality_docstring(ast.get_docstring(tree) or ""):
        return Finding(rel_path, "module", rel_path, 1, "missing", "low_quality_docstring")
    return Finding(
        rel_path,
        "module",
        rel_path,
        1,
        "required" if has_docstring else "missing",
        "module_purpose",
    )


def iter_symbol_nodes(tree: ast.Module) -> Iterable[tuple[ast.AST, ast.AST | None]]:
    """Yield class and function nodes with their direct parent node."""
    stack: list[tuple[ast.AST, ast.AST | None]] = [(node, tree) for node in tree.body]
    while stack:
        node, parent = stack.pop(0)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, parent
        if isinstance(node, ast.ClassDef):
            stack.extend((child, node) for child in node.body)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend((child, node) for child in node.body)


def symbol_finding(rel_path: str, node: ast.AST, parent: ast.AST | None) -> Finding:
    """Classify docstring requirements for a class, function, or method."""
    if isinstance(node, ast.ClassDef):
        return class_finding(rel_path, node)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return function_finding(rel_path, node, parent)
    raise TypeError(f"unsupported node: {node!r}")


def class_finding(rel_path: str, node: ast.ClassDef) -> Finding:
    """Classify class-level docstring coverage."""
    has_docstring = bool(ast.get_docstring(node))
    if has_docstring and has_low_quality_docstring(ast.get_docstring(node) or ""):
        return Finding(rel_path, "class", node.name, node.lineno, "missing", "low_quality_docstring")
    return Finding(
        rel_path,
        "class",
        node.name,
        node.lineno,
        "required" if has_docstring else "missing",
        "class_purpose",
    )


def function_finding(rel_path: str, node: ast.FunctionDef | ast.AsyncFunctionDef, parent: ast.AST | None) -> Finding:
    """Classify function or method docstring coverage according to the matrix."""
    has_docstring = bool(ast.get_docstring(node))
    status, reason = function_requirement(rel_path, node, parent)
    if has_docstring and status == "required" and has_low_quality_docstring(ast.get_docstring(node) or ""):
        return Finding(rel_path, function_kind(parent), node.name, node.lineno, "missing", "low_quality_docstring")
    if status == "required" and not has_docstring:
        status = "missing"
    return Finding(rel_path, function_kind(parent), node.name, node.lineno, status, reason)


def function_requirement(rel_path: str, node: ast.FunctionDef | ast.AsyncFunctionDef, parent: ast.AST | None) -> tuple[str, str]:
    """Return the requirement status and reason for a function-like node."""
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "exempt", "nested_function"
    if node.name in ORDINARY_DUNDER_NAMES:
        return "exempt", "ordinary_dunder"
    if node.name == "__init__":
        return "exempt", "covered_by_class_docstring"
    if has_decorator(node, "property") or node.name in ACCESSOR_NAMES:
        return "exempt", "accessor"
    if is_protocol_stub(parent, node):
        return "exempt", "protocol_stub"
    if is_test_assert(rel_path, node.name):
        return "exempt", "test_assert_contract_name"
    if is_test_fake_function(rel_path, node.name):
        return "exempt", "test_fake_helper"
    if node.name.startswith("_") and is_trivial_helper(node):
        return "exempt", "trivial_private_helper"
    return "required", "function_purpose"


def function_kind(parent: ast.AST | None) -> str:
    """Return a stable symbol kind for reporting."""
    return "method" if isinstance(parent, ast.ClassDef) else "function"


def has_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef, decorator_name: str) -> bool:
    """Detect a decorator by simple or attribute name."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == decorator_name:
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == decorator_name:
            return True
    return False


def is_protocol_stub(parent: ast.AST | None, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Detect method declarations inside Protocol classes."""
    if not isinstance(parent, ast.ClassDef):
        return False
    if not (parent.name.endswith("Protocol") or any(base_name(base) == "Protocol" for base in parent.bases)):
        return False
    return body_is_stub(node.body)


def has_low_quality_docstring(docstring: str) -> bool:
    """Return whether a docstring violates the anti-noise rules."""
    lowered = f" {docstring.casefold()} "
    return any(marker in lowered for marker in BANNED_DOCSTRING_MARKERS)


def base_name(node: ast.expr) -> str:
    """Return the final name segment for a base class expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def is_doc_expr(stmt: ast.stmt) -> bool:
    """Return whether a statement is a string docstring expression."""
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def body_is_stub(body: list[ast.stmt]) -> bool:
    """Return whether a function body only declares a stub."""
    body_without_doc = body[1:] if body and is_doc_expr(body[0]) else body
    return len(body_without_doc) == 1 and isinstance(body_without_doc[0], (ast.Pass, ast.Expr, ast.Raise))


def is_test_assert(rel_path: str, name: str) -> bool:
    """Detect validation assertion wrappers in test-agent scripts."""
    return rel_path.startswith("scripts/test_agent/") and name.startswith("assert_")


def is_test_fake_function(rel_path: str, name: str) -> bool:
    """Detect simple fake helpers in test-agent scripts."""
    lowered = name.lower()
    return rel_path.startswith("scripts/test_agent/") and any(marker in lowered for marker in ("fake", "stub", "mock"))


def is_trivial_helper(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a private helper is small enough to be self-explanatory."""
    body = node.body[1:] if node.body and is_doc_expr(node.body[0]) else node.body
    if len(body) > 1:
        return False
    if not body:
        return True
    statement = body[0]
    return isinstance(statement, (ast.Return, ast.Pass, ast.Raise))


def summarize(findings: list[Finding]) -> dict[str, int]:
    """Summarize findings by status for command output."""
    summary = {"required": 0, "missing": 0, "exempt": 0, "skipped_by_wave": 0}
    for finding in findings:
        summary[finding.status] = summary.get(finding.status, 0) + 1
    summary["total"] = len(findings)
    return summary


if __name__ == "__main__":
    main()
