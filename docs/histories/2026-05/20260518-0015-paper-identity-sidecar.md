## [2026-05-18 00:15] | Task: Add paper identity sidecar

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5.4`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 执行论文身份核验、arXiv 加速、程序规则 + GPT 复核和 100 篇测评机制的 Phase 1 计划。

### 🛠 Changes Overview

**Scope:** `packages/paper_identity`, `packages/sentiment`, `scripts/test_agent`, `scripts/eval`, `docs`

**Key Actions:**

- **Identity sidecar**: 新增论文身份状态模型、标题/作者相似度、确定性规则、OpenAlex work-first client、arXiv metadata client 和 GPT 复核入口。
- **arXiv governance**: Stage5 arXiv 标题补充搜索改为复用 metadata client 的同运行缓存和 `>=3.1s/request` 限速。
- **Validation**: 新增 `paper_identity.py` 合同测试并接入聚合入口，Stage5 增加共享缓存验证。
- **Evaluation scaffold**: 新增 100 篇测评模板生成、正常方案运行、纯 GPT baseline 和评分脚本。

### 🧠 Design Intent (Why)

第一期不重写 Stage4 作者识别主链路，而是先用 sidecar 生成可解释证据，避免破坏既有 `CitingPaper` / `AuthorProfile` 契约。arXiv 的“加速”通过缓存、复用 ID hint 和减少重复请求实现，不通过并发冲击官方 API。

### 📁 Files Modified

- `packages/paper_identity/`
- `packages/sentiment/fulltext.py`
- `scripts/test_agent/paper_identity.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/run.py`
- `scripts/eval/paper_identity_build_dataset.py`
- `scripts/eval/paper_identity_run_pipeline.py`
- `scripts/eval/paper_identity_run_llm_baseline.py`
- `scripts/eval/paper_identity_score.py`
- `docs/testing/stage-validation.md`
- `docs/RELIABILITY.md`
- `docs/ARCHITECTURE.md`
