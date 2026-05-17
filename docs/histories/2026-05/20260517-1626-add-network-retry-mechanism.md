## [2026-05-17 16:26] | Task: 增加全链路网络重试机制

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 每个遇到网络调用的地方都需要加重试机制，并讨论哪些地方需要加、重试是否需要大模型判断、重试结果是否需要大模型检查。

### 🛠 Changes Overview

**Scope:** 共享重试工具、学术 API 客户端、全文/GROBID/LLM 调用边界、阶段验证与稳定性文档

**Key Actions:**

- **[共享重试工具]**: 新增 `packages/shared/network_retry.py`，统一处理 `requests` / `urllib` 的 timeout、TLS/SSL、`429/5xx`、`Retry-After`、退避等待和中文 retry 日志。
- **[学术 API]**: 给 OpenAlex / DBLP 接入重试；Crossref 保留既有重试但补 runtime retry 日志；Semantic Scholar 保留原有 1 秒 1 次限流，不做双重包装。
- **[阶段链路]**: 给目标论文解析、全文候选下载、arXiv 全文候选搜索、GROBID health / PDF 解析和 LLM provider `.invoke()` 增加确定性重试。
- **[预算保护]**: 在阶段 4 作者画像中增加网络失败预算，避免 OpenAlex/DBLP 系统性故障时逐作者重试拖慢整轮分析。
- **[验证]**: 新增 `network_retry_contract.py` 并接入聚合入口，覆盖重试成功、不可重试状态、`Retry-After`、耗尽日志、OpenAlex/DBLP transient failure。

### 🧠 Design Intent (Why)

之前 OpenAlex 查询作者时出现 TLS/SSL EOF，导致实际存在的作者被降级为弱证据。这类问题属于瞬时传输层失败，应由确定性工程规则重试，而不是交给 LLM 判断。方案同时限制每类服务的尝试次数和预算，避免重试机制在作者批量查询、GROBID 大文件上传或严格限流 API 上造成副作用。

### 📁 Files Modified

- `packages/shared/network_retry.py`
- `packages/author_intel/clients/openalex.py`
- `packages/author_intel/clients/dblp.py`
- `packages/author_intel/service.py`
- `packages/citation_sources/clients/crossref.py`
- `apps/analyzer/resolve.py`
- `apps/analyzer/config.py`
- `apps/analyzer/nodes.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/grobid_client.py`
- `packages/sentiment/classifier.py`
- `packages/sentiment/llm_locator.py`
- `scripts/test_agent/network_retry_contract.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `docs/RELIABILITY.md`
- `docs/testing/stage-validation.md`
