## [2026-04-24 19:15] | Task: 补执行计划并修复文档 lint

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 这个是否需要跟踪 / 好的，请进行！

### 🛠 Changes Overview

**Scope:** 执行计划与产品规格文档

**Key Actions:**

- **补执行计划**: 将 `citation-analysis-mvp` 的 execution plan 写入 `docs/exec-plans/active/`
- **修复 Markdown lint**: 调整产品规格中的重复小标题，消除 CI 中的 `MD024` 错误

### 🧠 Design Intent (Why)

执行计划是当前项目进入实现阶段前的正式交付物，必须进入版本库。同时，远端 CI 已暴露 markdownlint 问题，需要先修复文档结构，避免后续提交继续失败。

### 📁 Files Modified

- `docs/product-specs/citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260424-1915-add-execution-plan-and-fix-markdownlint.md`
