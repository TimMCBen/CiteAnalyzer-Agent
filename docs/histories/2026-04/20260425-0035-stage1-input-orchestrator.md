## [2026-04-25 00:35] | Task: 完成阶段1输入解析与总流程骨架

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 现在执行阶段1，执行完后对TODO依次打勾。请注意，每一点TODO都进行一个本地提交。

### 🛠 Changes Overview

**Scope:** 阶段 1 代码骨架与执行计划

**Key Actions:**

- **建立核心对象**: 定义 `TargetPaper` 与 `AnalysisRequest`
- **建立入口骨架**: 搭建 `apps/analyzer` 并实现总智能体最小入口
- **实现输入解析**: 支持 DOI、论文 ID、标题、arXiv 输入兼容
- **实现状态收口**: 增加目标论文标准化、非法输入错误和标题不确定状态
- **预留后续接口**: 在总智能体中预留阶段 2 的文献爬取调用接口
- **完成验证**: 用本地样本验证 DOI、论文 ID、arXiv、标题和空输入路径

### 🧠 Design Intent (Why)

阶段 1 的目标不是直接接入外部数据源，而是先把总智能体的输入和核心对象稳定下来，让阶段 2 可以建立在清晰的标准化入口之上。

### 📁 Files Modified

- `apps/analyzer/__init__.py`
- `apps/analyzer/main.py`
- `apps/analyzer/orchestrator.py`
- `apps/analyzer/resolve.py`
- `packages/shared/__init__.py`
- `packages/shared/errors.py`
- `packages/shared/models.py`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260425-0035-stage1-input-orchestrator.md`
