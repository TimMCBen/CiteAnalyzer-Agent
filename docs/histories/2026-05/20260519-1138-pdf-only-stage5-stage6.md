## [2026-05-19 11:38] | Task: PDF-only Stage 5/6

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 不再需要 text 获取，只需要 PDF；按计划执行并测试。

### 🛠 Changes Overview

**Scope:** `apps/analyzer`, `packages/sentiment`, `packages/shared`, `scripts/test_agent`, `docs/testing`

**Key Actions:**

- **[PDF-only acquisition]**: Stage 5 仅接受 PDF artifact，不再把 markdown、普通文本、HTML、TeX 或摘要作为可分析文本源。
- **[No PDF text extraction]**: PDF 下载后只保存 raw PDF 和轻量 marker，不再用 `pypdf` 抽取正文文本作为 Stage 6 输入。
- **[GROBID-only PDF analysis]**: Stage 6 对 PDF 先走 GROBID；GROBID 未命中时不再回退到 PDF 抽取文本/规则文本定位。
- **[Runtime wording]**: 运行摘要将“全文获取”改为“PDF获取”，避免和旧 text/fulltext 口径混淆。
- **[Dependency cleanup]**: `pypdf` 不再被主链路使用，已从 CI 依赖中移除。
- **[Tests]**: Stage 5、Stage 6、Stage56、E2E 测试改为 PDF-only contract，并补充 arXiv PDF URL 样本。

### 🧠 Design Intent (Why)

旧流程同时存在 Stage 5 预抓文本、Stage 6 按需抓 PDF/文本、摘要 fallback 和 PDF 文本抽取，导致“全文获取”和“GROBID命中”的统计口径不一致。用户明确只需要 PDF 后，主链路收口为 PDF artifact -> GROBID -> 引用上下文/情感，减少 text fallback 带来的误判和日志混淆。

### 📁 Files Modified

- `apps/analyzer/nodes.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/models.py`
- `packages/sentiment/service.py`
- `packages/sentiment/__init__.py`
- `packages/sentiment/workflow.py`
- `packages/shared/runtime_logging.py`
- `requirements-ci.txt`
- `scripts/test_agent/e2e_mvp.py`
- `scripts/test_agent/e2e_real_smoke.py`
- `scripts/test_agent/stage1.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `scripts/test_agent/stage7.py`
- `docs/ARCHITECTURE.md`
- `docs/QUALITY_SCORE.md`
- `docs/design-docs/citation-analysis-maps.md`
- `docs/testing/stage-validation.md`
- `README.md`

### ✅ Verification

- `python scripts/test_agent/run.py --log detail`
