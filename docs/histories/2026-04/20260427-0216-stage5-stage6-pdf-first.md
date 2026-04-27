## [2026-04-27 02:16] | Task: 切换 stage5/stage6 到 PDF-first 方向

### 🤖 Execution Context

- **Agent ID**: `Codex / Ralph session`
- **Base Model**: `gpt-5`
- **Runtime**: `OMX Ralph mode`

### 📥 User Query

> stage5 要优先下载 pdf 而不是 tex；先整理 5/6 重构方案，然后 ralph，最后先提交一版，再整理所有 doc 文件后再提交。随后用户明确选择我给出的“方案 B”，要求直接启动。

### 🛠 Changes Overview

**Scope:** `packages/sentiment`、`scripts/test_agent`、`README.md`、`docs/`

**Key Actions:**

- **[Stage5 PDF-first]**: 调整全文候选优先级，显式优先 PDF，并把 arXiv e-print/source 链接统一改写为 PDF/HTML/abs 候选。
- **[去掉 tar 默认产物]**: 不再把 `tar` / `extracted/` 当作 stage5 的默认正式抓取结果。
- **[Stage6 PDF 主路径]**: 保持 `PDF -> GROBID -> context` 为主路径，并在 GROBID 不可用时回退到普通文本窗口定位。
- **[验证脚本同步]**: 更新 stage5/stage6 本地验证脚本，确保验证的是 PDF-first 行为，而不是旧的 TeX-first 假设。
- **[文档同步]**: 更新 README、架构、测试说明、执行计划和质量评分文档。

### 🧠 Design Intent (Why)

用户最新选择覆盖了上一轮“保留 tar sidecar”的思路，因此这轮设计目标是把阶段 5/6 的默认主路径收口到更简单、更一致的 PDF-first 方案。这样 stage5 的职责更清楚，stage6 也能围绕 GROBID 建立更稳定的主路径，同时通过回退逻辑保留本地验证与非理想环境下的可用性。

### 📁 Files Modified

- `packages/sentiment/fulltext.py`
- `packages/sentiment/workflow.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/testing/stage-validation.md`
- `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
- `docs/QUALITY_SCORE.md`
- `docs/histories/2026-04/20260427-0216-stage5-stage6-pdf-first.md`
