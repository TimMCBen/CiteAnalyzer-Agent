## [2026-04-29 01:35] | Task: 用 ralplan 收口 stage3 与 stage5/stage6 契约

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI in repo workspace`

### 📥 User Query

> `$ralplan` 探索阶段3，完善阶段5和6

### 🛠 Changes Overview

**Scope:** `docs/exec-plans/active/`, `docs/testing/`, `scripts/test_agent/`

**Key Actions:**

- **[冻结阶段编号契约]**: 把主 MVP 计划收口到 `stage5 = 全文抓取`、`stage6 = 引用定位与情感分析`、`stage7 = 报告生成`，并把端到端联调改成最终交付里程碑。
- **[给 stage3 明确当前结论]**: 在阶段 3 计划里补上“本轮维持 manual/debug only，不进入默认 MVP 实现”的结论和后续升级门槛。
- **[同步验证入口真相]**: 把 `scripts/test_agent/run.py` 纳入 `stage5.py` / `stage6.py`，同时更新 `docs/testing/stage-validation.md`，避免继续把它们写成 TODO。
- **[补齐下游引用关系]**: 修正阶段 4 对下游阶段的引用，并把阶段 5/6 计划中的旧验证状态同步到本轮真实结果。

### 🧠 Design Intent (Why)

这轮不是单纯补文档，而是在做一次小范围 contract migration。仓库里的 README、架构、history 和可运行脚本已经收口到新的 `stage5/6/7` 语义，但主 MVP 计划、测试说明和聚合验证入口还停留在旧编号上。如果不把这些活跃契约同步到同一套说法，后续协作会持续在“阶段到底指什么”上浪费时间。

### 📁 Files Modified

- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-04-26-stage3-google-scholar-supplement.md`
- `docs/exec-plans/active/2026-04-26-stage4-scholar-intel-agent.md`
- `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
- `docs/testing/stage-validation.md`
- `scripts/test_agent/run.py`
