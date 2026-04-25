## [2026-04-25 19:35] | Task: 实现阶段 2 文献爬取基础骨架

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 现在执行阶段2的开发！

### 🛠 Changes Overview

**Scope:** `packages/`, `scripts/`, `docs/`

**Key Actions:**

- **实现阶段 2 核心对象**: 新增 `CitingPaper`、`SourceTrace`、`FetchSummary` 和抓取结果对象。
- **实现最小抓取服务**: 新增标准化、去重、来源追踪与状态挂接逻辑。
- **补阶段 2 验证**: 将 `scripts/test_agent/stage2.py` 从 TODO 改成真实断言脚本，并接入聚合验证入口。

### 🧠 Design Intent (Why)

阶段 2 当前最需要的是一个可验证的最小服务边界，而不是一上来把真实外部 API、状态图节点和所有降级逻辑同时塞进一轮实现。先把领域对象、服务输入输出、去重和来源追踪落稳，后续再接真实源时风险会小很多。

### 📁 Files Modified

- `packages/citation_sources/__init__.py`
- `packages/citation_sources/models.py`
- `packages/citation_sources/normalize.py`
- `packages/citation_sources/dedupe.py`
- `packages/citation_sources/service.py`
- `packages/shared/models.py`
- `scripts/test_agent/stage2.py`
- `scripts/test_agent/run.py`
- `docs/testing/stage-validation.md`
- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260425-1935-implement-stage2-foundation.md`
