# 稳定性与可运维性

这里用来定义项目的运行质量底线。

建议维护的内容包括：

- 启动、健康检查和基本可用性要求。
- 日志、指标、链路的采集和访问约定。
- timeout、retry、backoff 的默认策略。
- 本地和 CI 的关键路径验证方式。
- 常见故障、排查路径和恢复步骤。

CI/CD 流程结构和 release 自动化的默认方案，统一写在 `docs/CICD.md`。
项目自己的测试入口、阶段验证和样本约定，统一写在 `docs/testing/`。

## 当前 runtime 日志约定

- 正式 analyzer 运行链路使用 `CITE_ANALYZER_RUNTIME_LOG=quiet|brief|detail` 控制中文可读日志。
- 测试阶段脚本继续使用 `CITE_ANALYZER_STAGE_LOG=brief|detail`，两套变量不要混用。
- 外部 API live smoke 入口 `scripts/test_agent/e2e_real_smoke.py` 是 opt-in，不接入默认 `scripts/check-project.sh`。
- Stage 7 国家/地区解析的真实 LLM smoke 是 GitHub CI 专用检查；本地默认跳过，CI 需要 `API_KEY`、`BASE_URL` 和 `MODEL=gpt-5.4`。
- 0 施引、OpenAlex 单作者失败、GROBID 命中 / 未命中和 Semantic Scholar 限速等关键分支由 `scripts/test_agent/runtime_logging_contract.py` 的 fake/fixture contract 稳定覆盖。

## 当前网络重试约定

- 网络重试由确定性规则控制，不由 LLM 判断是否重试，也不由 LLM 检查重试结果。
- 可重试错误包括 timeout、TLS/SSL EOF、连接重置、临时 `URLError`、HTTP `429/500/502/503/504`。
- 不重试无效输入、`400/401/403/404`、解析错误、schema 错误或业务层 `unknown` 结果。
- Semantic Scholar 客户端保留自己的 1 秒 1 次限流和重试逻辑，不应在调用层再包一层重试。
- GROBID `/isalive` 可短重试；`/processFulltextDocument` 是大文件 POST，只允许极少次数重试。
- OpenAlex / DBLP 作者画像查询有单请求重试和阶段级失败预算，避免批量作者场景被系统性网络失败拖慢。
- 论文身份核验 sidecar 的 OpenAlex work 查询使用缓存和短重试；真实批量测评可通过 `OPENALEX_API_KEY` / `OPENALEX_MAILTO` 进入认证或 polite 路径；失败只标记该论文身份为 `error/lookup_failed`，不能被 GPT 当作“不存在”。
- arXiv metadata 查询统一经过 `ArxivMetadataClient`，默认 `>= 3.1s/request`，并维护同运行 ID 缓存、标题正缓存和标题负缓存。
- Stage5 的 arXiv 标题全文候选搜索只消费共享 metadata client，不再直接绕过限速发 `requests.get()`；加速来自减少重复请求，而不是并发打 arXiv API。
- 重试 detail 日志使用 `retry.wait`，耗尽时使用 `retry.exhausted`，字段应包含 `service`、`operation`、`attempt`、`max_attempts`、`delay_s`、`reason`、`impact`。
- 重试契约由 `scripts/test_agent/network_retry_contract.py` 覆盖，并已接入 `scripts/test_agent/run.py` 聚合入口。
