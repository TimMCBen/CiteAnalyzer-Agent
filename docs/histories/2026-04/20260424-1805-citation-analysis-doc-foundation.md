## [2026-04-24 18:05] | Task: 完善引用分析项目文档基线

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 持续帮我迭代和修改，并提交一版 git

### 🛠 Changes Overview

**Scope:** 仓库级产品规格与架构文档

**Key Actions:**

- **补齐产品规格**: 新增并反复收口 `citation-analysis-mvp`，明确 MVP 目标、边界、验收标准和关键规则
- **重写架构文档**: 将模板架构替换为“总智能体 + 子智能体”的真实项目架构，并补齐仓库结构、依赖边界、降级策略与数据模型

### 🧠 Design Intent (Why)

先把项目从模板状态推进到“可以进入 execution plan”的文档基线。当前阶段最重要的是让产品目标、系统结构和仓库边界稳定下来，避免后续实现时反复返工。

### 📁 Files Modified

- `docs/product-specs/citation-analysis-mvp.md`
- `docs/ARCHITECTURE.md`
- `docs/histories/2026-04/20260424-1805-citation-analysis-doc-foundation.md`
