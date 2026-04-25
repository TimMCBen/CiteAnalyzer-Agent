## [2026-04-25 18:55] | Task: 细化阶段 2 执行计划

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 细化阶段二，写进 plan 文档，最好是新开一个，而不是在原来的基础上写。

### 🛠 Changes Overview

**Scope:** `docs/exec-plans/`, `docs/histories/`

**Key Actions:**

- **新开阶段 2 子计划**: 新增独立的阶段 2 执行计划文档，不在原 MVP 总计划中继续堆细节。
- **补齐执行切片**: 将文献爬取智能体拆成数据对象、客户端、标准化、去重、集成、验证六个切片。
- **明确验证与降级**: 为阶段 2 单独定义脚本验证入口、可降级场景和不可静默吞掉的失败。

### 🧠 Design Intent (Why)

主 MVP 计划适合保留阶段级视图，不适合继续承载单阶段的实现边界、数据对象和降级策略。把阶段 2 细化单独落到子计划里，后续实现时更容易按切片推进，也不会让总计划失去可读性。

### 📁 Files Modified

- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/histories/2026-04/20260425-1855-detail-stage2-plan.md`
