# 测试文档索引

这里专门放项目级测试说明，不和模板级 `CI/CD` 骨架混写。

## 当前内容

- `stage-validation.md`：按阶段维护 `scripts/test_agent/` 的验证约定与当前覆盖范围。

## 约定

- 模板级流水线入口保留在 `docs/CICD.md`。
- 项目自己的测试入口、样本、阶段覆盖率和运行说明写在本目录。
- 当前仓库的项目级验证钩子是 `scripts/check-project.sh`。
