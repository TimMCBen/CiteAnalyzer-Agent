## [2026-04-26 22:15] | Task: 收紧 stage2 输入契约

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> stage2 的输入需要加上对应论文的名字（title）。

### 🛠 Changes Overview

**Scope:** `packages/citation_sources/`, `scripts/test_agent/`, `docs/histories/`

**Key Actions:**

- **收紧 stage2 输入**: 要求 `target_paper.title` 必须存在，且 `target_paper.resolve_status` 必须是 `resolved`。
- **补输出摘要**: `FetchSummary` 新增 `target_title`、`target_doi`、`target_resolve_status`。
- **补测试**: stage2 验证新增“缺 title 必须拒绝”的断言。

### 🧠 Design Intent (Why)

既然 stage1 已经负责把目标论文验真并补齐标题，stage2 就不应该再接受一个只有 DOI 没有标题的弱目标对象。把这个契约写死后，后续阶段能更稳定地知道自己到底在分析哪篇目标论文。

### 📁 Files Modified

- `packages/citation_sources/models.py`
- `packages/citation_sources/service.py`
- `scripts/test_agent/stage2.py`
- `docs/histories/2026-04/20260426-2215-require-target-title-in-stage2.md`
