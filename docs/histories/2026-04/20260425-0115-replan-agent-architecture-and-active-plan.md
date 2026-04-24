## [2026-04-25 01:15] | Task: 重规划智能体架构与执行计划

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 重写 active plan，不要和之前那一次挂钩；调研 LangChain / LangGraph 并写入 references；按当前修改提交一版

### 🛠 Changes Overview

**Scope:** 架构、执行计划、参考资料

**Key Actions:**

- **撤回旧实现骨架**: 删除原阶段 1 输入解析与总流程代码骨架，避免继续沿用旧的固定工作流路线
- **重写架构文档**: 将架构表达收口为“论文被引分析智能体 + 原始命名不变的子智能体”
- **重写 active plan**: 以 LangGraph 状态编排和 LangChain 工具/模型辅助为新路线重写执行计划
- **补 references**: 新增并整理 LangChain / LangGraph 参考资料，以及针对当前项目的框架组合参考

### 🧠 Design Intent (Why)

项目当前需要从“固定顺序工作流”转向“总智能体按需调度子智能体”的实现路线，因此需要先在文档层面完成方向收口，再继续后续实现。

### 📁 Files Modified

- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/product-specs/citation-analysis-mvp.md`
- `docs/references/README.md`
- `docs/references/langchain-overview.md`
- `docs/references/langgraph-overview.md`
- `docs/references/langchain-langgraph-for-citeanalyzer.md`
- `docs/histories/2026-04/20260425-0115-replan-agent-architecture-and-active-plan.md`
