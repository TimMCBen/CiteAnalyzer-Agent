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
- 0 施引、OpenAlex 单作者失败、GROBID 命中 / 未命中和 Semantic Scholar 限速等关键分支由 `scripts/test_agent/runtime_logging_contract.py` 的 fake/fixture contract 稳定覆盖。
