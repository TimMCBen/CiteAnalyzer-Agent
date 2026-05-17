## [2026-05-18 05:09] | Task: Add Python purpose comments

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 为 Python 代码补用途注释：只说明每个文件、函数或类做什么；先形成规则文件，多智能体讨论后执行。

### 🛠 Changes Overview

**Scope:** `apps/`, `packages/`, `scripts/`, `docs/`

**Key Actions:**

- **Comment rules**: 新增 `docs/CODE_COMMENTING_RULES.md`，明确用途型 docstring 的覆盖矩阵、豁免规则和防噪音约束。
- **Contract check**: 新增 `scripts/test_agent/comment_contract.py`，用 AST 检查模块、类、函数 docstring 覆盖，并纳入 `scripts/test_agent/run.py` 聚合验证。
- **Purpose docstrings**: 为纳入范围的 Python 文件补模块、类、函数用途 docstring，避免实现细节型行内解释。
- **Validation docs**: 更新阶段验证说明和质量评分，记录注释契约已成为默认测试入口。

### 🧠 Design Intent (Why)

用户要求的是“帮助读者快速知道职责”的注释，而不是逐行解释实现。规则文件和 contract 先落地，可以防止后续继续产生低信息模板句，也让 CI 能持续守住用途注释覆盖。

### 📁 Files Modified

- `docs/CODE_COMMENTING_RULES.md`
- `scripts/test_agent/comment_contract.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `docs/testing/stage-validation.md`
- `docs/QUALITY_SCORE.md`
- `apps/**/*.py`
- `packages/**/*.py`
- `scripts/eval/**/*.py`
- `scripts/test_agent/**/*.py`
