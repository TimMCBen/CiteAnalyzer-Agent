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

### 阶段 3、阶段 4 与阶段 7

- 目录中已预留：
  - `stage3.py`
  - `stage4.py`
  - `stage7.py`
- 当前状态：TODO，占位保留给后续阶段实现时补齐。

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

- 阶段 6
  - 当前原型能力：
    - `LangGraph` 工作流
    - GROBID `PDF -> TEI XML -> biblStruct/ref -> context` 主路径
    - GROBID 不可用时的普通文本窗口回退
    - 直接 TeX bibliography / cite-key 兼容路径
    - 目标引文显式高亮 `**...**`
  - 当前验证：
    - `python ./scripts/test_agent/stage6.py`
    - `STAGE6_REAL_CITING5=1 python ./scripts/test_agent/stage6.py`
    - `STAGE6_GROBID_CITING5=1 python ./scripts/test_agent/stage6.py`
  - 当前状态：
    - 已实现本地夹具验证
    - 已接入 `scripts/test_agent/run.py` 聚合验证

## 维护原则

- 阶段测试脚本属于项目实现层，不应直接写进模板级 `CICD` 说明。
- 新增项目测试入口时，优先更新本目录，再决定是否需要把入口接入 `scripts/check-project.sh`。
- execution plan 中的阶段验证任务应和这里保持一致。
