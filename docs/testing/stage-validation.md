# 阶段验证说明

当前仓库把 MVP 的阶段验证脚本放在 `scripts/test_agent/`。

## 入口

- 项目级统一入口：`bash ./scripts/check-project.sh`
- 阶段聚合入口：`python ./scripts/test_agent/run.py`
- 阶段 1 单独运行：`python ./scripts/test_agent/stage1.py`

日志模式：

- 默认 `brief`：输出阶段开始、通过、跳过、失败和完成摘要。
- 详细 `detail`：额外输出样本路径、候选数量、产物路径、降级信息和 live smoke 状态。
- 聚合入口：`python ./scripts/test_agent/run.py --log detail`
- 项目级入口：`CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`
- 单阶段入口：`CITE_ANALYZER_STAGE_LOG=detail python ./scripts/test_agent/stage6.py`
- PowerShell：`$env:CITE_ANALYZER_STAGE_LOG="detail"; python ./scripts/test_agent/stage6.py`

日志允许少量 emoji 和分段符号辅助阅读，但自动化检查只依赖 `START` / `PASS` / `FAIL` / `SKIP` / `DETAIL` 等稳定文本 token。

正式 analyzer 运行日志：

- 运行链路使用 `CITE_ANALYZER_RUNTIME_LOG=quiet|brief|detail` 控制中文 runtime 日志，默认 `brief`。
- `CITE_ANALYZER_RUNTIME_LOG` 服务 `apps/analyzer/` 正式分析入口；`CITE_ANALYZER_STAGE_LOG` 只服务 `scripts/test_agent/` 阶段验证入口。
- RuntimeLogger contract：`python ./scripts/test_agent/runtime_logging_contract.py`
- opt-in live smoke：`python ./scripts/test_agent/e2e_real_smoke.py --target https://arxiv.org/abs/2504.19162 --max-citations 3 --log detail`
- `e2e_real_smoke.py` 依赖外部 API 和当前网络，不接入默认 `run.py`、`check-project.sh` 或默认 CI。
- 0 施引路径由 `runtime_logging_contract.py` 的 fake/fixture 稳定验证；不要把实时外部数据库的当前施引数作为固定验收。

当前 `run.py` 仍只聚合：

- `import_contract.py`
- `llm_prompt_contract.py`
- `network_retry_contract.py`
- `stage1.py`
- `stage2.py`
- `stage4.py`
- `stage5.py`
- `stage6.py`
- `stage56_integration.py`
- `stage7.py`
- `e2e_mvp.py`

并已通过独立集成烟测：

- `stage56_integration.py`

并把以下入口显式标记为待接入：

- `stage3.py`
- `stage8.py`

## 当前覆盖

### 阶段 1

- 脚本：`scripts/test_agent/import_contract.py`
- 覆盖：
  - 阶段 1 / 报告层相关导入链不应因为缺少 `bs4` 而在导入期失败
  - 防止阶段 5 / 6 的可选全文依赖泄漏到阶段 1 默认入口

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
  - `stage8.py`
  - `e2e_mvp.py`
- 当前状态：
  - `stage3.py`：TODO，占位保留给补充源探索
  - `stage8.py`：TODO，占位保留给后续端到端验证扩展；当前 MVP E2E 入口为 `e2e_mvp.py`

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
    - 已接入 `scripts/test_agent/run.py` 聚合验证

### 阶段 7

- 脚本：`scripts/test_agent/stage7.py`
- 当前覆盖：
  - `ReportArtifact` contract
  - HTML / JSON / PDF 报告导出路径
  - 趋势、国家/地区来源、机构、学者、情感、降级说明区块
  - ECharts 图表容器、情感饼图、图表数据 fallback、机构 Top N 文案
  - 独立 PDF renderer 的真实产物存在性
  - 规则国家/地区解析 trace 与真实 LLM 国家/地区解析 smoke；运行前必须在仓库根目录 `.env` 或环境变量中提供 `API_KEY`、`BASE_URL`、`MODEL`
  - Stage 7 live smoke 会断言实际生效的 `MODEL=gpt-5.4`，不是任意真实模型
  - 分析摘要、重要学者表格、代表性引用语境
  - `report.json` 原始 `charts` 契约保持不变，HTML 才生成展示层图表
  - `fetch_summary` / `source_trace` / `state.errors` / 弱标注 `confidence_note` 的报告暴露
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

### Runtime Logger

- 脚本：`scripts/test_agent/runtime_logging_contract.py`
- 当前覆盖：
  - Semantic Scholar 默认字段不包含 `authors.name` / `citingPaper.authors.name`
  - arXiv 版本号在 Semantic Scholar client 边界归一化
  - runtime logger 对 API key / authorization 等敏感字段脱敏
  - 0 施引 fake 样本最终生成 HTML / JSON / PDF 报告，且不写入 `state.errors`
  - OpenAlex 单作者异常输出 `WARN` 且标注 `impact=single_author`
  - GROBID 命中 / 未命中输出中文日志
- 当前状态：
  - 已实现 fake/fixture contract
  - 不访问真实外部 API

### Network Retry

- 脚本：`scripts/test_agent/network_retry_contract.py`
- 当前覆盖：
  - TLS/SSL EOF、timeout 等瞬时错误会重试后成功
  - `404` 等不可重试 HTTP 状态不会等待或重复请求
  - `Retry-After` 能控制等待时间
  - 重试耗尽会产生结构化异常和中文 `retry.exhausted` 日志
  - OpenAlex / DBLP 客户端在 transient failure 后能重试成功
- 当前状态：
  - 已实现 fake contract
  - 已接入 `scripts/test_agent/run.py` 聚合验证
  - 不访问真实外部 API

- 脚本：`scripts/test_agent/e2e_real_smoke.py`
- 当前覆盖：
  - 正式 analyzer live 路径的中文 runtime 日志
  - `--max-citations` 控制真实 Semantic Scholar 请求规模
  - 最终报告 HTML / JSON 产物存在
- 当前状态：
  - opt-in live smoke
  - 不接入默认聚合入口

## 维护原则

- 阶段测试脚本属于项目实现层，不应直接写进模板级 `CICD` 说明。
- 新增项目测试入口时，优先更新本目录，再决定是否需要把入口接入 `scripts/check-project.sh`。
- execution plan 中的阶段验证任务应和这里保持一致。
- `stage7.py` 与 `e2e_mvp.py` 必须保持职责拆分：前者只做报告 contract 验证，后者只做真实样本总控验证。
- analyzer 集成烟测可以独立存在于聚合入口之外，只要其职责和断言点在本文件中写清。
- 新增或调整阶段脚本时，应同步维护 `scripts/test_agent/stage_logging.py` 的统一日志输出，不要在脚本里各自拼装不同格式。
