# 阶段验证说明

当前仓库把 MVP 的阶段验证脚本放在 `scripts/test_agent/`。

## 入口

- 项目级统一入口：`bash ./scripts/check-project.sh`
- 阶段聚合入口：`python ./scripts/test_agent/run.py`
- 阶段 1 单独运行：`python ./scripts/test_agent/stage1.py`

## 当前覆盖

### 阶段 1

- 脚本：`scripts/test_agent/stage1.py`
- 覆盖：
  - 标题线索请求
  - DOI 请求
  - arXiv 请求
  - OpenAlex 论文 ID 请求
  - 非论文被引分析请求

### 阶段 2 到阶段 7

- 阶段 2
  - 脚本：`scripts/test_agent/stage2.py`
  - 覆盖：
    - 多源记录合并与去重
    - 来源追踪输出
    - 单来源失败时的部分结果降级

- 阶段 3 到阶段 7
- 目录中已预留：
  - `stage3.py`
  - `stage4.py`
  - `stage5.py`
  - `stage6.py`
  - `stage7.py`
- 当前状态：TODO，占位保留给后续阶段实现时补齐。

## 维护原则

- 阶段测试脚本属于项目实现层，不应直接写进模板级 `CICD` 说明。
- 新增项目测试入口时，优先更新本目录，再决定是否需要把入口接入 `scripts/check-project.sh`。
- execution plan 中的阶段验证任务应和这里保持一致。
