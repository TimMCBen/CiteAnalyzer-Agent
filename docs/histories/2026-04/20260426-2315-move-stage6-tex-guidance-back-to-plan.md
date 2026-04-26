## [2026-04-26 23:15] | Task: 清理 stage6 tex skill 落点

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 这个 skill 没什么用，只是 stage6 的运行说明书，不如放回原来的 exec-plan。

### 🛠 Changes Overview

**Scope:** `docs/exec-plans/`, `.codex/skills/`, `docs/histories/`

**Key Actions:**

- **迁移方法说明**: 把 TeX 引用定位方法从 `.codex/skills/` 迁回当前引用情感分析执行计划。
- **删除薄 skill**: 去掉没有独立运行价值的 `stage6-tex-citation` skill。
- **收口文档边界**: 让阶段方法论回到项目执行计划，而不是绑定 Codex 运行时。

### 🧠 Design Intent (Why)

这套内容本质上是项目内引用情感分析阶段的实现细则，而不是跨项目复用的独立 skill。把它放回 exec-plan，更符合“业务规则属于仓库文档，运行时适配属于 skill”的分层。

### 📁 Files Modified

- `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
- `docs/histories/2026-04/20260426-2315-move-stage6-tex-guidance-back-to-plan.md`
- `.codex/skills/stage6-tex-citation/SKILL.md`
