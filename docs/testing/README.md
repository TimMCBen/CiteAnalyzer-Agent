# 测试文档索引

这里专门放项目级测试说明，不和模板级 `CI/CD` 骨架混写。

## 当前内容

- `stage-validation.md`：按阶段维护 `scripts/test_agent/` 的验证约定与当前覆盖范围。

## 约定

- 模板级流水线入口保留在 `docs/CICD.md`。
- 项目自己的测试入口、样本、阶段覆盖率和运行说明写在本目录。
- 当前仓库的项目级验证钩子是 `scripts/check-project.sh`。
- 项目级验证默认使用简略日志；需要详细日志时使用 `CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`。
- 阶段脚本日志格式由 `scripts/test_agent/stage_logging.py` 统一维护，允许少量 emoji 辅助阅读，但自动化判断应依赖稳定文本 token。
- 正式 analyzer runtime 日志使用 `CITE_ANALYZER_RUNTIME_LOG=quiet|brief|detail`，和阶段测试日志变量分开。
- `scripts/test_agent/runtime_logging_contract.py` 是 CI-safe fake/fixture contract；`scripts/test_agent/e2e_real_smoke.py` 是 opt-in live smoke，不进入默认项目级验证。
