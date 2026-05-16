## [2026-05-07 19:06] | Task: fix ci import chain

### 🤖 Execution Context

- **Agent ID**: `Codex CLI session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex + oh-my-codex`

### 📥 User Query

> 检查 ci 为什么会报错！请修复

### 🛠 Changes Overview

**Scope:** `apps/analyzer/`, `packages/sentiment/`, `scripts/test_agent/`, `docs/testing/`, `README.md`

**Key Actions:**

- **定位 CI 根因**: GitHub Actions 失败于 `Run base CI checks`，根因是阶段 1 导入链提前触发 `packages/sentiment/fulltext.py`，导致 CI runner 在缺少 `bs4` 时直接失败。
- **修复导入链**: 将 `packages.sentiment` 改为轻量包初始化，并在 `apps/analyzer/nodes.py` 中恢复可 monkeypatch 的懒加载 wrapper，切断阶段 1 对阶段 5 可选依赖的提前要求。
- **补回归验证**: 新增 `scripts/test_agent/import_contract.py`，并纳入 `run.py` 默认聚合入口，锁定“阶段 1 导入不依赖 bs4”的契约。
- **同步文档**: 更新 README 与阶段验证文档，反映新的 `import_contract.py` 聚合入口。

### 🧠 Design Intent (Why)

这次不通过给 CI 临时安装依赖来掩盖问题，而是修正错误的导入边界：阶段 1 的默认验证不应要求阶段 5 的 HTML 解析依赖。这样既修当前 CI，也防后续类似回归。

### 📁 Files Modified

- `packages/sentiment/__init__.py`
- `apps/analyzer/nodes.py`
- `scripts/test_agent/import_contract.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `README.md`
- `docs/testing/stage-validation.md`
