## [2026-04-25 22:05] | Task: 实现阶段 2 真实客户端与图接线

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 请你继续完成阶段二，可以列多个智能体协作完成！

### 🛠 Changes Overview

**Scope:** `packages/`, `apps/`, `scripts/`, `docs/`

**Key Actions:**

- **并行实现真实客户端**: 增加 `SemanticScholarClient` 与 `CrossrefClient`，分别负责主抓取和元数据补全。
- **重构服务主线**: 将阶段 2 服务改成 `Semantic Scholar` 主抓取、`Crossref` enrichment 的职责分工。
- **接入 analyzer graph**: 增加阶段 2 节点、图和 `run_stage2_analysis()` 入口，并为阶段 2 测试增加可选 live smoke。

### 🧠 Design Intent (Why)

阶段 2 已有最小骨架，但真正的边界还没有经历真实客户端接入的检验。先把两个外部源客户端落成薄客户端，再通过 service 层接到 graph 和脚本验证中，可以把“主抓取”和“元数据补全”的职责正式固定下来。

### 📁 Files Modified

- `packages/citation_sources/clients/__init__.py`
- `packages/citation_sources/clients/semantic_scholar.py`
- `packages/citation_sources/clients/crossref.py`
- `packages/citation_sources/__init__.py`
- `packages/citation_sources/service.py`
- `packages/citation_sources/normalize.py`
- `packages/citation_sources/dedupe.py`
- `apps/analyzer/nodes.py`
- `apps/analyzer/graph.py`
- `apps/analyzer/main.py`
- `scripts/test_agent/stage2.py`
- `docs/testing/stage-validation.md`
- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260425-2205-implement-live-stage2-clients.md`
