## [2026-04-26 21:45] | Task: 增加 stage1 目标论文校验

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> stage1 需要在最后验证 doi/title/arxiv id 是否正确或合法；如果没有 title 必须补 title。规则是：doi 用 Crossref，arxiv 用 arXiv API，paper_id 暂不实现，title 用 Crossref 和 arXiv API 各搜一次，当前只考虑完全匹配。

### 🛠 Changes Overview

**Scope:** `apps/analyzer/`, `scripts/test_agent/`, `docs/histories/`

**Key Actions:**

- **新增解析节点**: 在 stage1/stage2 图里增加目标论文校验与补全节点。
- **按类型校验**: `doi -> Crossref`，`arxiv -> arXiv API`，`paper_id -> unresolved`，`title -> arXiv exact match 优先，Crossref exact match 兜底`。
- **补全 title**: 合法 DOI / arXiv / title 命中后，输出结构化 `TargetPaper` 并补齐 `title`。

### 🧠 Design Intent (Why)

stage1 只做线索抽取还不够，后续阶段需要的是已经验真、并尽量补齐标题的目标论文对象。把这一步前移到 stage1，能减少后续阶段猜标题或重复联网校验。

### 📁 Files Modified

- `apps/analyzer/resolve.py`
- `apps/analyzer/nodes.py`
- `apps/analyzer/graph.py`
- `scripts/test_agent/stage1.py`
- `docs/histories/2026-04/20260426-2145-add-stage1-target-resolution.md`
