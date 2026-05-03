## [2026-05-04 10:45] | Task: 刷新 MVP baseline 口径

### Execution Context

- **Agent ID**: `codex-main-session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX ralph`

### User Query

> `$ralph` 按要求开发，并另外设置一个智能体检查开发进度，检查 docs 写文件的情况。

### Changes Overview

**Scope:** docs / test entrypoints / execution plans

**Key Actions:**

- **统一 baseline 文档口径**: 同步 README、testing、architecture、product spec 和主 MVP plan，明确 `stage6` 本轮冻结为单上下文。
- **拆清验证入口职责**: 把 `stage7.py` 定义为报告 contract / fixture 验证入口，并新增 `scripts/test_agent/e2e_mvp.py` 作为独立真实样本总控入口占位。
- **同步聚合入口现状**: 更新 `scripts/test_agent/run.py` 的 pending 列表与对应文档说明，避免把它误写成已完成的最终聚合入口。
- **补正式收口路线**: 新增 active execution plan，记录 MVP 收口的分支顺序、owned files 和 verifier gate。

### Design Intent (Why)

当前仓库的主要问题不是功能完全缺失，而是 baseline 文档、测试入口和计划口径已经开始漂移。先把 `stage6`、`stage7`、`e2e_mvp.py` 和 `run.py` 的职责冻结下来，后续阶段 4、总控接回、阶段 7 和 E2E 开发才不会继续踩在过期约定上返工。

### Files Modified

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-05-04-mvp-closure-roadmap.md`
- `docs/histories/2026-05/20260504-1045-refresh-mvp-baseline.md`
- `docs/product-specs/citation-analysis-mvp.md`
- `docs/testing/stage-validation.md`
- `scripts/test_agent/e2e_mvp.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/stage7.py`
