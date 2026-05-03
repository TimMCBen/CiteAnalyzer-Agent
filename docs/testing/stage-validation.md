# 阶段验证说明

当前仓库把 MVP 的阶段验证脚本放在 `scripts/test_agent/`。

## 入口

- 项目级统一入口：`bash ./scripts/check-project.sh`
- 阶段聚合入口：`python ./scripts/test_agent/run.py`
- 阶段 1 单独运行：`python ./scripts/test_agent/stage1.py`

当前 `run.py` 仍只聚合：

- `stage1.py`
- `stage2.py`
- `stage4.py`
- `stage5.py`
- `stage6.py`
- `stage7.py`
- `e2e_mvp.py`

并已通过独立集成烟测：

- `stage56_integration.py`

并把以下入口显式标记为待接入：

- `stage3.py`

## 当前覆盖

### 阶段 1

- 脚本：`scripts/test_agent/stage1.py`
- 覆盖：
  - 标题线索请求
  - DOI 请求
  - arXiv 请求
  - OpenAlex 论文 ID 请求
  - 非论文被引分析请求

### 阶段 3、阶段 7 与 E2E

- 目录中已预留：
  - `stage3.py`
  - `stage7.py`
  - `e2e_mvp.py`
- 当前状态：
  - `stage3.py`：TODO，占位保留给补充源探索

### 阶段 4

- 脚本：`scripts/test_agent/stage4.py`
- 当前覆盖：
  - `OpenAlex` 主画像链路
  - `DBLP` 辅助补全链路
  - 高影响力 / 重量级 / 弱标注规则
  - 缺失 `h-index` 时的“证据不足”路径
- 当前状态：
  - 已实现本地夹具验证
  - 已接入 `scripts/test_agent/run.py` 聚合验证

- 阶段 5
  - 当前原型能力：
    - `PDF-first` 全文抓取
    - PDF / HTML / LaTeX 解析
    - 本地落盘 `raw artifact + parsed txt`
    - 不再把 `tar` / `extracted/` 视为默认正式产物
    - 当全文不可获取时，返回恢复建议并在可用时退回摘要
  - 当前验证：
    - `python ./scripts/test_agent/stage5.py`
    - `STAGE5_FETCH_LIVE=1 python ./scripts/test_agent/stage5.py`
  - 当前状态：
    - 已实现本地夹具验证
    - 已接入 `scripts/test_agent/run.py` 聚合验证

### 阶段 5 / 阶段 6 总控接回

- 脚本：`scripts/test_agent/stage56_integration.py`
- 当前覆盖：
  - `apps/analyzer/nodes.py` 的 stage4 / stage5 / stage6 节点挂接
  - `packages/shared/models.py` 的 scholar / fulltext / sentiment 状态字段
  - analyzer 阶段 5 / 6 的逐篇调度 glue
  - 当前状态：
    - 已实现本地夹具烟测
    - 当前尚未接入 `scripts/test_agent/run.py` 聚合验证

### 阶段 7

- 脚本：`scripts/test_agent/stage7.py`
- 当前覆盖：
  - `ReportArtifact` contract
  - HTML / JSON 报告导出路径
  - 趋势、来源、学者、情感、降级说明区块
  - fixture 驱动的报告级验证
- 当前状态：
  - 已实现本地夹具验证
  - 已接入 `scripts/test_agent/run.py` 聚合验证

- 阶段 6
  - 当前原型能力：
    - `LangGraph` 工作流
    - GROBID `PDF -> TEI XML -> biblStruct/ref -> context` 主路径
    - GROBID 不可用时的普通文本窗口回退
    - 直接 TeX bibliography / cite-key 兼容路径
    - 目标引文显式高亮 `**...**`
    - 当前 MVP 契约冻结为“每篇 citing paper 只返回一条主 `CitationContext`”
  - 当前验证：
    - `python ./scripts/test_agent/stage6.py`
    - `STAGE6_REAL_CITING5=1 python ./scripts/test_agent/stage6.py`
    - `STAGE6_GROBID_CITING5=1 python ./scripts/test_agent/stage6.py`
  - 当前状态：
    - 已实现本地夹具验证
    - 已接入 `scripts/test_agent/run.py` 聚合验证

### E2E

- 脚本：`scripts/test_agent/e2e_mvp.py`
- 当前覆盖：
  - `run_analysis()` 通过 analyzer 总控跑完整链路
  - 使用已保存的真实 stage2 样本与本地 fixture 驱动 stage4 / stage5 / stage6 / stage7
  - 报告产物导出路径、unknown 降级与最终 `report_generated` 状态
- 当前状态：
  - 已实现 fixture-backed 全链路验证
  - 已接入 `scripts/test_agent/run.py` 聚合验证

## 维护原则

- 阶段测试脚本属于项目实现层，不应直接写进模板级 `CICD` 说明。
- 新增项目测试入口时，优先更新本目录，再决定是否需要把入口接入 `scripts/check-project.sh`。
- execution plan 中的阶段验证任务应和这里保持一致。
- `stage7.py` 与 `e2e_mvp.py` 必须保持职责拆分：前者只做报告 contract 验证，后者只做真实样本总控验证。
- analyzer 集成烟测可以独立存在于聚合入口之外，只要其职责和断言点在本文件中写清。
