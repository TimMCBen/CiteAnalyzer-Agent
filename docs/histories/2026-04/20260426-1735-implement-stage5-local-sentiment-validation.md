## [2026-04-26 17:35] | Task: 实现阶段5本地验证链路

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 按照现在的计划先开发阶段5；如果抓不到论文可以尝试 arXiv，但测试先用 `docs/generated/stage2-live-10.1145.3368089.3409740.json`，先不用自己抓；每做完一个任务就本地提交。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `packages/shared/`, `scripts/test_agent/`, `docs/`

**Key Actions:**

- **实现阶段5核心包**: 新增文本来源选择、目标引用定位、规则情感分类和结果汇总的本地优先链路。
- **补齐阶段5验证脚本**: 直接读取阶段2真实样本，并注入本地 Markdown / LaTeX 正文夹具验证四类标签和降级路径。
- **同步仓库文档**: 更新阶段验证说明和架构文档，记录阶段5已落地的代码边界。
- **后续扩展**: 接入真实 PDF / HTML / LaTeX 解析、arXiv 补充抓取，以及 LLM zero-shot 间接引用定位 fallback。

### 🧠 Design Intent (Why)

阶段5先用本地回归固定输入输出边界和 `unknown` 语义，再把真实全文抓取与 LLM fallback 挂在同一条 service 链路上。这样既能保留稳定测试，又不会把真实抓取和语义定位永远留在“以后再说”。

### 📁 Files Modified

- `packages/shared/models.py`
- `packages/sentiment/__init__.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/models.py`
- `packages/sentiment/reference_locator.py`
- `packages/sentiment/classifier.py`
- `packages/sentiment/service.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/run.py`
- `docs/testing/stage-validation.md`
- `docs/ARCHITECTURE.md`
- `docs/histories/2026-04/20260426-1735-implement-stage5-local-sentiment-validation.md`
