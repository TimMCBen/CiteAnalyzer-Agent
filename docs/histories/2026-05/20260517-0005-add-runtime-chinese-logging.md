## [2026-05-17 00:05] | Task: add runtime Chinese logging

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 开始执行中文 runtime 日志可读性方案。

### 🛠 Changes Overview

**Scope:** analyzer runtime logging, citation source compatibility, runtime validation scripts, testing docs

**Key Actions:**

- **RuntimeLogger**: 新增正式 analyzer 运行链路中文日志、脱敏、`contextvars` 注入和 runtime-only options。
- **0 施引收口**: stage4 / stage5 / stage6 在空 `citing_papers` 时写入合法空产物，stage7 仍可生成报告。
- **API 兼容**: Semantic Scholar 字段从 `authors.name` 改为 `authors`，并在客户端边界归一化 arXiv 版本号。
- **验证入口**: 新增 fake/fixture `runtime_logging_contract.py` 与 opt-in live `e2e_real_smoke.py`。

### 🧠 Design Intent (Why)

用户需要能用中文直接理解正式分析流程中的阶段进度、外部 API 调用、限速等待、局部降级和最终摘要。实现时把测试阶段日志和正式 runtime 日志分层，避免把 logger 写入业务状态；同时修复已知 live smoke 阻塞项，保证日志验证不被 Semantic Scholar 字段或 arXiv 版本号问题干扰。

### 📁 Files Modified

- `packages/shared/runtime_logging.py`
- `apps/analyzer/main.py`
- `apps/analyzer/nodes.py`
- `apps/analyzer/resolve.py`
- `packages/citation_sources/clients/semantic_scholar.py`
- `packages/citation_sources/service.py`
- `packages/author_intel/clients/openalex.py`
- `packages/author_intel/service.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/service.py`
- `packages/sentiment/workflow.py`
- `packages/sentiment/grobid_client.py`
- `scripts/test_agent/runtime_logging_contract.py`
- `scripts/test_agent/e2e_real_smoke.py`
- `README.md`
- `docs/QUALITY_SCORE.md`
- `docs/RELIABILITY.md`
- `docs/SECURITY.md`
- `docs/testing/README.md`
- `docs/testing/stage-validation.md`
