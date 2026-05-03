## [2026-05-04 11:45] | Task: 实现 stage4 学者识别主链路

### Execution Context

- **Agent ID**: `codex-main-session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX ralph`

### User Query

> `$ralph` 按要求开发，并另外设置一个智能体检查开发进度，检查 docs 写文件的情况。

### Changes Overview

**Scope:** author_intel / shared models / stage validation / docs sync

**Key Actions:**

- **实现 stage4 包结构**: 新增 `packages/author_intel/`，包含模型、标准化、规则、服务和 `OpenAlex` / `DBLP` 客户端。
- **补共享 contract**: 在 `packages/shared/models.py` 中加入 `AuthorProfile`、`ScholarLabel`、`AuthorSummary`，为后续 analyzer 集成留出稳定状态字段。
- **增加正式验证脚本**: 新增 `scripts/test_agent/stage4.py`，覆盖高影响力、重量级、弱标注与证据不足路径。
- **同步验证入口与文档**: 让 `run.py` 聚合 `stage4.py`，并同步 README、testing、architecture、主 MVP plan 的当前实现状态。

### Design Intent (Why)

stage4 当前最需要的是稳定 contract，而不是直接把 author-intel 粘进 analyzer。先把作者候选展开、画像补全、启发式规则和本地验证脚本固定下来，后续接总控时才不会一边改 state 一边猜规则。

### Files Modified

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-05/20260504-1145-implement-stage4-author-intel.md`
- `docs/testing/stage-validation.md`
- `packages/author_intel/__init__.py`
- `packages/author_intel/clients/__init__.py`
- `packages/author_intel/clients/dblp.py`
- `packages/author_intel/clients/openalex.py`
- `packages/author_intel/models.py`
- `packages/author_intel/normalize.py`
- `packages/author_intel/rules.py`
- `packages/author_intel/service.py`
- `packages/shared/models.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/stage4.py`
