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
- **后续扩展**: 已进一步改为 LLM 主导的阶段5链路，默认测试直接调用真实模型，并将全文入口切到 arXiv-first。

### 🧠 Design Intent (Why)

阶段5现在以 LLM 为中心：先固定本地可重复全文夹具，再让真实模型负责参考文献匹配、正文定位和情感判断；同时把全文获取优先级调整成 arXiv-first，避免 DOI 落地页充当伪正文。

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
