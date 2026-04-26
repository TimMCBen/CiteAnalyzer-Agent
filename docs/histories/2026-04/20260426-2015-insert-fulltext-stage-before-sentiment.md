## [2026-04-26 20:15] | Task: 增加全文抓取阶段

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 请你增加一个阶段，这个阶段用于抓取全文！

### 🛠 Changes Overview

**Scope:** `docs/exec-plans/`, `docs/testing/`, `docs/ARCHITECTURE.md`, `scripts/test_agent/`, `packages/sentiment/`

**Key Actions:**

- **新增阶段 5**: 把“全文抓取与文本解析”拆成独立阶段，位于学者识别之后、情感分析之前。
- **后续阶段顺延**: 原情感分析改为阶段 6，报告改为阶段 7，联调改为阶段 8。
- **同步测试入口**: 新增 `scripts/test_agent/stage5.py` 做全文抓取验证，原情感分析验证顺延到 `stage6.py`，并更新聚合入口。
- **补本地落盘**: 阶段 5 抓到的全文文本会保存到 `downloaded-papers/stage5/`，作为阶段产物保留给后续阶段消费。

### 🧠 Design Intent (Why)

全文获取和情感分析是两类不同职责：前者解决“有没有可处理文本”，后者解决“文本里怎么找引用并判断态度”。把它们拆成两个阶段后，边界更清楚，失败原因也更容易定位。

### 📁 Files Modified

- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-04-26-stage5-fulltext-acquisition-agent.md`
- `docs/exec-plans/active/2026-04-26-stage6-citation-sentiment-agent.md`
- `docs/testing/stage-validation.md`
- `docs/ARCHITECTURE.md`
- `scripts/test_agent/run.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `scripts/test_agent/stage7.py`
- `scripts/test_agent/stage8.py`
- `packages/sentiment/__init__.py`
- `docs/histories/2026-04/20260426-2015-insert-fulltext-stage-before-sentiment.md`
