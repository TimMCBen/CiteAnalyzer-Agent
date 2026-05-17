# 运行日志中文可读性改进方案

## 目标

把当前“能调试但不够好读”的阶段日志，改造成中文用户能直接理解的运行说明。日志需要同时满足两类需求：

- 人读：用中文解释每个阶段在做什么、为什么跳过、哪里降级、最后产出了什么。
- 机器测：继续保留稳定 token，例如 `START`、`DETAIL`、`WARN`、`SKIP`、`FAIL`、`DONE`，方便 contract 测试和 CI 搜索。

本方案只规划，不直接实现代码。后续执行时应在现有 `feat/stage-logging-modes` 分支上继续推进。

## 当前日志诊断

### 已有能力

- `scripts/test_agent/stage_logging.py:7` 已定义 `CITE_ANALYZER_STAGE_LOG`，支持 `brief` / `detail` 两种模式。
- `scripts/test_agent/stage_logging.py:20` 到 `scripts/test_agent/stage_logging.py:50` 已集中封装 `StageLogger`，输出 `START`、`PASS`、`DETAIL`、`SKIP`、`FAIL`、`DONE`。
- `docs/exec-plans/active/2026-05-16-stage-logging-modes.md:27` 到 `docs/exec-plans/active/2026-05-16-stage-logging-modes.md:29` 已规划测试阶段脚本通过环境变量选择简略或详细日志。
- `apps/analyzer/graph.py:57` 到 `apps/analyzer/graph.py:74` 显示正式全链路按 `parse_user_query -> resolve_target_paper -> fetch_citation_candidates -> analyze_author_intel -> fetch_fulltext_documents -> analyze_citation_sentiments -> generate_report` 推进。

### 主要问题

- 当前 `StageLogger` 主要面向测试脚本，输出形态类似 `DETAIL stage6 | contexts=3`，对用户缺少中文解释。
- `apps/analyzer/nodes.py:114` 到 `apps/analyzer/nodes.py:230` 的正式运行节点没有统一 runtime logger，用户只能从最终 state 或异常推断发生了什么。
- `apps/analyzer/main.py:36` 到 `apps/analyzer/main.py:37` 当前 `run_analysis()` 直接走 stage7 图；`apps/analyzer/graph.py:57` 到 `apps/analyzer/graph.py:74` 当前无条件串行推进 stage2/4/5/6/7。
- `apps/analyzer/nodes.py:141`、`apps/analyzer/nodes.py:150`、`apps/analyzer/nodes.py:180`、`apps/analyzer/nodes.py:200` 的下游节点当前会在空 `citing_papers` 或缺少上游结果时抛错。因此“0 篇施引文献正常跳过下游”不是当前行为，必须作为控制流改造写入执行范围。
- `packages/citation_sources/clients/semantic_scholar.py:180` 到 `packages/citation_sources/clients/semantic_scholar.py:212` 的请求、重试、超时、HTTP 错误没有结构化中文说明。
- `packages/author_intel/service.py:35` 到 `packages/author_intel/service.py:44` 会捕获 OpenAlex / DBLP 单作者查询异常，但只把英文错误拼进 `errors`，用户不容易判断这是“单个作者弱降级”还是“整体失败”。
- `packages/sentiment/fulltext.py:39` 到 `packages/sentiment/fulltext.py:108` 才是全文来源选择、fallback 到 abstract、无文本可用的真实落点。
- `packages/sentiment/service.py:15` 到 `packages/sentiment/service.py:96` 才是 `unknown` 情感计数、abstract-only、no-text 的汇总落点。
- `packages/sentiment/workflow.py:54` 到 `packages/sentiment/workflow.py:70` 会尝试 GROBID PDF 匹配，但命中、未命中和服务不可用主要藏在 `evidence_note` / `grobid_note`。
- `packages/sentiment/workflow.py:128` 到 `packages/sentiment/workflow.py:154` 的情感分类失败会降级为 `unknown`，但运行日志没有把“无法判断”的原因用中文讲清楚。
- `packages/citation_sources/clients/semantic_scholar.py:16` 到 `packages/citation_sources/clients/semantic_scholar.py:22` 当前使用 `authors.name` / `citingPaper.authors.name`，已知会被官方 Graph API 拒绝；这不是日志问题，但会阻塞 live smoke，必须作为前置修复。
- `apps/analyzer/resolve.py:75` 到 `apps/analyzer/resolve.py:95` 的 arXiv 解析可能回填带版本号的 arXiv ID；`packages/citation_sources/clients/semantic_scholar.py:144` 到 `packages/citation_sources/clients/semantic_scholar.py:154` 当前会把该值原样拼进 `ARXIV:`，必须在 Semantic Scholar client 边界再次归一化。
- `apps/analyzer/nodes.py:121` 当前将 stage2 `max_results=20` 写死；如果新增 `e2e_real_smoke.py --max-citations 3`，必须先设计 runtime-only options 传递通路。
- `apps/analyzer/resolve.py:32` 到 `apps/analyzer/resolve.py:95`、`apps/analyzer/resolve.py:142` 到 `apps/analyzer/resolve.py:181` 已经涉及 Crossref / arXiv 网络解析，但当前计划也需要把 resolver 边界纳入中文日志，否则最早的外部失败仍不可读。

### 最近真实测试暴露出的解释需求

- `arXiv:2504.19162` 可以跑完整链路：阶段 2 找到 3 篇施引文献，阶段 4 查询 36 位作者，阶段 5 下载 3 篇全文，阶段 6 产出 3 条上下文，最终生成 HTML 报告。
- 最近一次人工 live 测试中 `arXiv:2602.04144` 在阶段 2 后无下游输入，因为当时 Semantic Scholar 返回 0 篇施引文献。该样本只能作为人工观察，不作为永久 live gate；稳定 0 施引语义由 fake/fixture contract 验证。
- GROBID 健康检查可以成功，但真实匹配只命中部分 citing paper。日志应逐篇说明 `GROBID 命中 / 未命中 / 降级到文本匹配`。
- OpenAlex 查询个别作者时可能出现 TLS 连接中断。日志应解释为“外部服务连接中途断开，已记录为该作者画像弱证据或失败，不代表全流程失败”。
- Semantic Scholar API 有 1 request / second 限制。日志应在 detail 模式说明限速等待和重试，不应把等待误解成卡死。

## 范围

包含：

- 为正式 analyzer 运行链路新增中文 runtime logger，覆盖 `apps/analyzer` 和关键业务包调用边界。
- 明确支持 0 施引文献的正常收口：下游阶段输出 `SKIP`，同时填充空的作者画像、情感摘要和报告输入，避免无条件串行图在空输入时报错。
- 前置修复 Semantic Scholar 字段兼容和 arXiv ID 版本号归一化，保证 live smoke 不被已知外部 API 适配问题阻塞。
- 增加 runtime-only options 传递能力，至少支持 `max_citations`，供 live smoke 控制真实请求规模。
- 扩展测试阶段日志的中文展示，但不破坏现有 `StageLogger` 稳定 token。
- 输出目标级总结块，解释每篇目标论文最终结果、跳过原因、报告路径和降级项。
- 将外部 API 调用、限速等待、重试、降级、局部失败、最终摘要做成统一中文事件。
- 新增正式 analyzer live smoke 入口，和测试 `StageLogger` contract 分层验证，证明中文日志出现且不会泄露密钥。

不包含：

- 不引入第三方 logging / rich / structlog 依赖。
- 不做日志文件持久化，除非后续单独增加 `--log-file` 或 JSONL 计划。
- 不改变分析结果数据模型和报告格式。
- 不把所有底层异常翻译成完整中文错误库，本轮只覆盖当前链路高频事件。
- 不在日志中打印 API key、完整请求 header、`.env` 原文或可恢复的敏感配置。

## 设计原则

1. 中文说明优先，机器 token 保底。
2. emoji 只做视觉辅助，不作为测试依据。
3. `brief` 模式只讲阶段和结论；`detail` 模式才展开 API、重试、逐篇、逐作者细节。
4. 所有外部服务失败必须标注影响范围：单作者、单篇 citing paper、单阶段或全流程。
5. 降级不是失败。日志必须显式区分 `WARN`、`SKIP`、`FAIL`。
6. 日志不吞异常、不改变退出码、不替代最终报告。
7. Live smoke 只验证日志语义和流程可读性，不把实时外部引用数量写成永久验收事实。

## 推荐方案

### 新增 runtime logger

新增 `packages/shared/runtime_logging.py`，用于正式 analyzer 运行链路；保留 `scripts/test_agent/stage_logging.py` 给测试脚本使用。

建议 API：

```python
logger = RuntimeLogger(component="analyzer", mode="brief")
logger.stage_start("stage2", "抓取施引文献", target=target_label)
logger.detail("semantic_scholar.request", "正在请求 Semantic Scholar 施引列表", paper_id=paper_id, limit=3)
logger.warn("openalex.lookup", "OpenAlex 查询作者时连接中断，已降级为弱证据", author="Lei Bai", impact="single_author")
logger.skip("stage6", "没有施引文献，跳过引用上下文和情感分析", reason="no_citing_papers")
logger.stage_done("stage7", "报告生成完成", html=html_path)
logger.summary(...)
```

传递机制：

- 使用 `contextvars.ContextVar` 保存当前 runtime logger。
- `apps/analyzer/main.py` 在 `run_analysis()` / `run_stage*_analysis()` 入口根据 `CITE_ANALYZER_RUNTIME_LOG` 配置 logger。
- `apps/analyzer/nodes.py` 和业务包通过 `get_runtime_logger()` 读取当前 logger。
- `get_runtime_logger()` 在未注入上下文时必须返回 no-op logger，业务包不得自行判空，也不得因为缺少 runtime logger 改变业务行为。
- 不把 logger 写入 `AnalysisState`，避免破坏 state 序列化和报告输入。
- `ContextVar` 生命周期必须由入口包装层负责：`token = set_runtime_logger(logger)` 后用 `try/finally reset_runtime_logger(token)`，避免同一 Python 进程内连续调用时串日志上下文。
- `run_analysis()` 和各 `run_stage*_analysis()` 必须用 set/reset 或 context manager 包住 `app.invoke(state)`；不得只在 `run_analysis()` 包装而漏掉单阶段入口。
- 失败路径必须 `catch -> logger.fail(...) -> logger.summary(..., status="failed") -> raise`，只补充中文失败说明，不吞异常、不改退出码。
- Runtime-only options 也用 contextvar 或同一 runtime context 管理，例如 `AnalysisRuntimeOptions(max_citations=3)`；`fetch_citation_candidates_node` 从 runtime options 读取 `max_citations`，缺省仍为当前 `20`。
- Runtime-only options 不写入 `AnalysisState`，避免污染报告输入和状态序列化。
- 后续如果做常驻 Web 服务，再把 contextvar 配置收口到请求级 middleware。

输出示例：

```text
▶ START 阶段2 | 抓取施引文献 | target=arXiv:2504.19162
ℹ DETAIL semantic_scholar.request | 正在请求 Semantic Scholar 施引列表 | limit=3
✅ DONE 阶段2 | 找到 3 篇施引文献 | semantic=3 crossref_enriched=2
⚠ WARN 阶段4 | OpenAlex 查询作者 Lei Bai 时 TLS 连接中断，已降级为弱证据 | impact=single_author
⏭ SKIP 阶段6 | Semantic Scholar 当前返回 0 篇施引文献，下游情感分析无输入 | reason=no_citing_papers
```

### 保留测试 logger，但共享格式思想

- `scripts/test_agent/stage_logging.py` 继续负责阶段验证脚本。
- 新 runtime logger 可复用相同 token 和模式名，避免用户学两套语义。
- 如果后续发现重复过多，再抽出轻量 formatter；第一步不要过度抽象。

### 日志等级与中文语义

| token | 中文含义 | 典型用途 |
| --- | --- | --- |
| `START` | 开始一个阶段或目标 | 目标论文解析、抓取、作者画像、全文、GROBID、报告 |
| `DETAIL` | 详细过程 | API 请求、限速等待、候选数、逐篇命中情况 |
| `PASS` | 测试断言通过 | 仅测试脚本使用 |
| `DONE` | 阶段完成 | 产生了可继续流转的状态或报告 |
| `WARN` | 可恢复问题 | OpenAlex TLS 断开、GROBID 未命中、单篇全文缺失 |
| `SKIP` | 有原因跳过 | 0 篇施引文献、未启用 live smoke、无全文 |
| `FAIL` | 阻塞失败 | 目标论文无法解析、主链路完全无结果且无法继续 |

### 阶段输出模板

#### 阶段 1：输入理解与目标论文解析

```text
▶ START 阶段1 | 理解用户输入
✅ DONE 阶段1 | 已识别目标论文 | type=arxiv query=2504.19162
```

如果解析失败：

```text
❌ FAIL 阶段1 | 无法识别目标论文线索，请提供 DOI、arXiv 链接或标题 | reason=target_missing
```

#### 阶段 2：施引文献抓取

```text
▶ START 阶段2 | 抓取施引文献 | source=Semantic Scholar + Crossref
ℹ DETAIL semantic_scholar.rate_limit | 等待 1.10 秒以遵守每秒最多 1 次请求限制
✅ DONE 阶段2 | 找到 3 篇施引文献 | semantic=3 crossref_enriched=2 deduped=3
```

0 结果：

```text
⏭ SKIP 阶段2下游 | Semantic Scholar 当前返回 0 篇施引文献，作者画像、全文和情感分析没有输入 | target=arXiv:2602.04144
```

#### 阶段 4：作者画像与重量级学者标注

```text
▶ START 阶段4 | 查询施引作者画像 | authors=36
⚠ WARN openalex.lookup | OpenAlex 查询作者 Lei Bai 时 TLS 连接中断，已改用 DBLP 或弱证据 | impact=single_author
✅ DONE 阶段4 | 完成作者画像 | matched=28 weak=8 heavyweight=0 high_impact=2
```

#### 阶段 5：全文获取

```text
▶ START 阶段5 | 获取施引论文全文 | citing_papers=3
ℹ DETAIL fulltext.fetch | citing-1 使用 PDF 来源并已保存 | path=downloaded-papers/stage5/...
⚠ WARN fulltext.fetch | citing-2 未找到全文，后续情感可能无法判断 | impact=single_paper
✅ DONE 阶段5 | 全文获取完成 | available=3 missing=0
```

#### 阶段 6：GROBID / 引用上下文 / 情感

```text
▶ START 阶段6 | 提取引用上下文并判断情感 | documents=3
ℹ DETAIL grobid.health | GROBID 服务可用 | url=http://localhost:8070/api
✅ DONE grobid.match | citing-1 命中目标论文参考文献结构 | evidence=biblStruct+bibr
⚠ WARN grobid.match | citing-2 未命中 GROBID 结构，已降级到文本/LLM 定位 | impact=single_paper
✅ DONE 阶段6 | 情感分析完成 | neutral=3 positive=0 critical=0 unknown=0
```

#### 阶段 7：报告生成

```text
▶ START 阶段7 | 生成 HTML / JSON 报告
✅ DONE 阶段7 | 报告生成完成 | html=generated-reports/2504-19162/report.html
```

### 目标级总结块

每篇目标论文结束后输出一个中文摘要块。detail 模式显示完整；brief 模式显示压缩版。

```text
===== 📄 分析结果摘要 =====
目标论文: arXiv:2504.19162
施引文献: 3 篇
作者画像: 36 位作者，28 位有外部画像证据
全文获取: 3/3
GROBID命中: 1/3
引用情感: 中性 3 / 正向 0 / 批评 0 / 未知 0
降级说明: OpenAlex 单作者查询失败 1 次，已记录为弱证据
报告路径: generated-reports/2504-19162/report.html
==========================
```

0 结果目标：

```text
===== 📄 分析结果摘要 =====
目标论文: fixture:no-citations
施引文献: 0 篇
流程状态: 已正常结束，但没有下游分析输入
原因说明: Semantic Scholar 当前没有返回该目标论文的施引记录
下一步建议: 可稍后重试，或补充 DOI / 标题进行交叉解析
==========================
```

## 关键文件与实施切片

### 切片 1：运行日志基础设施

涉及文件：

- `packages/shared/runtime_logging.py`
- `packages/shared/__init__.py`
- `scripts/test_agent/stage_logging.py`

工作：

- 新增 `RuntimeLogger`，支持 `CITE_ANALYZER_RUNTIME_LOG=brief|detail|quiet`，默认 `brief`。
- 新增 runtime context helper，例如 `set_runtime_logger()`、`reset_runtime_logger()`、`get_runtime_logger()`、`set_runtime_options()`、`get_runtime_options()`。
- `get_runtime_logger()` 默认返回 no-op logger；no-op logger 接受全部同名方法但不输出。
- 提供 context manager 包装入口，确保 `ContextVar` token 总能 reset。
- 新增 `AnalysisRuntimeOptions`，首个字段为 `max_citations: int | None`，用于 live smoke 控制真实请求规模。
- 为 runtime logger 定义统一 token、中文阶段名、分隔符、敏感字段过滤。
- `quiet` 仅隐藏普通进度，不隐藏 `WARN` / `FAIL` / 最终摘要。
- 保持 `CITE_ANALYZER_STAGE_LOG` 给测试脚本，避免和 runtime 模式混淆。

### 切片 2：analyzer 节点接入阶段日志

涉及文件：

- `apps/analyzer/main.py`
- `apps/analyzer/nodes.py`
- `apps/analyzer/graph.py`

工作：

- 在 `run_analysis()` 或图构建入口创建 logger，并让节点可以读取。
- 在 `parse_user_query`、`resolve_target_paper_node`、`fetch_citation_candidates_node`、`analyze_author_intel_node`、`fetch_fulltext_documents_node`、`analyze_citation_sentiments_node`、`generate_report_node` 前后输出中文阶段日志。
- 对没有施引文献的情况增加明确 `SKIP` 日志，并实现 no-op 下游状态填充：
  - `analyze_author_intel_node` 遇到空 `citing_papers` 时不抛错，写入 `author_profiles=[]`、`scholar_labels=[]`、`author_summary=AuthorSummary()`。
  - `fetch_fulltext_documents_node` 遇到空 `citing_papers` 时不抛错，写入 `fulltext_documents={}`。
  - `analyze_citation_sentiments_node` 遇到空 `citing_papers` 时不抛错，写入 `citation_contexts=[]`、`sentiment_summary=SentimentSummary(total_candidates=0)`。
  - `generate_report_node` 允许上述空摘要输入生成 0 施引报告，不能再把“0 施引”误判为缺少上游结果。
- 0 施引是正常结束，不写入 `state["errors"]`；如需持久化跳过原因，写入非错误 note 或 fetch/report provenance，不能污染 `manual_attention_items`。
- stage4 / stage5 / stage6 各自输出 `SKIP`，因为它们确实没有输入；stage2 也可以输出一次总括性“下游将跳过”，但不能只在 stage2 输出。
- no-op 节点状态字段应明确区分跳过与完成，例如 `author_intel_skipped_no_citations`、`fulltext_skipped_no_citations`、`citation_sentiments_skipped_no_citations`，避免把“未分析”伪装成“已分析完成”。
- `fetch_citation_candidates_node` 使用 runtime options 中的 `max_citations`，缺省仍为 `20`，使 `e2e_real_smoke.py --max-citations 3` 真实控制 stage2 请求规模。
- 保持现有业务 state 数据结构，不把 logger 写成业务状态的强依赖。

### 切片 3：外部 API 与降级解释

涉及文件：

- `apps/analyzer/resolve.py`
- `packages/citation_sources/clients/semantic_scholar.py`
- `packages/citation_sources/service.py`
- `packages/author_intel/clients/openalex.py`
- `packages/author_intel/service.py`
- `packages/sentiment/grobid_client.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/service.py`
- `packages/sentiment/workflow.py`

工作：

- Resolver：记录 Crossref / arXiv 目标解析请求、成功来源、失败降级和 unresolved 原因；避免最早的外部网络失败仍然只暴露英文异常。
- Semantic Scholar：记录请求目标、limit、HTTP 状态、429 / 5xx 重试、限速等待，不打印 API key。
- OpenAlex：逐作者失败时输出 `WARN`，明确 `impact=single_author`。
- Fulltext：在 `select_text_source()` 和 `fetch_fulltext_document()` 输出全文命中、候选失败、fallback 到 abstract、no text available 的中文原因。
- GROBID：输出 health、逐篇命中、未命中、不可用和 fallback 路径。
- 情感分析：`unknown` 必须带中文原因，例如“没有找到引用上下文”或“分类器失败”。

### 切片 4：真实样本 smoke 输出

涉及文件：

- 新增 `scripts/test_agent/e2e_real_smoke.py`
- 新增或扩展 `scripts/test_agent/runtime_logging_contract.py`
- `scripts/test_agent/e2e_mvp.py`
- `docs/testing/stage-validation.md`

工作：

- 新增 `e2e_real_smoke.py` 作为正式 runtime logger 的 live smoke 入口；现有 `e2e_mvp.py` 仍保持 fixture-backed 回归职责。
- `e2e_real_smoke.py` 是 opt-in live smoke，不接入 `scripts/test_agent/run.py`、`scripts/check-project.sh` 或默认 CI gate。
- `runtime_logging_contract.py` 是 fake/fixture、CI-safe contract，可以纳入默认或手动回归；它不访问真实外部 API。
- 新增 fake/fixture contract，稳定触发 0 施引、OpenAlex 异常、GROBID 命中/未命中、Semantic Scholar 限速/重试日志，不让 CI 依赖外部 API 波动。
- live smoke 默认使用 `arXiv:2504.19162` 或调用者指定目标验证中文日志语义；0 施引语义固定由 `runtime_logging_contract.py` 的 fake/fixture 样本验证。
- 对 `2504.19162` 验证“完整链路样本出现完整摘要字段”，不硬编码实时施引数量必须等于 3。
- 如果某个 live 目标当前确实返回 0 施引，`e2e_real_smoke.py` 可以手动观察 skip 摘要，但这不是固定验收项。
- smoke 必须尊重 Semantic Scholar 每秒最多 1 次请求限制。

最小可测断言：

| 场景 | 稳定触发手段 | 最小断言 |
| --- | --- | --- |
| Semantic Scholar 限速 / 请求 | fake SemanticScholar client 或 monkeypatch `_sleep_before_retry()` | 输出包含 `DETAIL semantic_scholar`、`限速` 或 `重试`，且不包含 API key |
| OpenAlex TLS / 单作者失败 | fake OpenAlex client 对指定作者抛 `ssl.SSLError` 或 `URLError` | 输出包含 `WARN openalex.lookup`、作者名、`impact=single_author` |
| GROBID 命中 | fixture PDF/TEI 或 monkeypatch `locate_reference_context_from_grobid_pdf()` 返回 `context_text` | 输出包含 `GROBID`、`命中`、`citing_paper_id` |
| GROBID 未命中 / fallback | monkeypatch 返回空 `context_text` 或抛异常 | 输出包含 `GROBID`、`未命中` 或 `不可用`、`降级` |
| 0 施引跳过 | fake citation service 返回 `citing_papers=[]` | 输出包含 `SKIP`、`0 篇施引文献`，最终 `status=report_generated`，HTML / JSON 报告路径存在 |

### 切片 5：相关问题单独修复或纳入执行

下面两个问题升格为 live smoke 前置修复，不再等失败后临时判断：

- `packages/citation_sources/clients/semantic_scholar.py:16` 到 `packages/citation_sources/clients/semantic_scholar.py:22` 当前使用 `authors.name` / `citingPaper.authors.name`，官方 Graph API 已知会返回 unsupported fields；本轮必须改为 `authors` / `citingPaper.authors` 并加 contract。
- `apps/analyzer/nodes.py:29` 到 `apps/analyzer/nodes.py:31` 的 arXiv 正则会去掉版本号，但 Semantic Scholar 客户端在 `packages/citation_sources/clients/semantic_scholar.py:144` 到 `packages/citation_sources/clients/semantic_scholar.py:154` 仍应确保不会把 `2504.19162v2` 传给 `ARXIV:` 查询；本轮必须在 Semantic Scholar client `_candidate_identifiers()` 边界再次归一化 arXiv ID 并加 contract。

触发条件和关闭条件：

- `authors.name` gate 命中：Semantic Scholar resolve / citation fetch 因 `fields` 参数返回 400，错误包含 unsupported / unrecognized fields。关闭条件：默认字段不再包含 `.name` 子字段，fake contract 覆盖字段字符串，live smoke 不再因该字段 400。
- arXiv version gate 命中：带版本号输入或 resolver 回填的 `2504.19162v2` 进入 `ARXIV:` 查询，导致 404 / resolve fail / citation fetch fail。关闭条件：Semantic Scholar client 对 `source_ids["arxiv"]` 和 `paper_query` 都执行版本号归一化，contract 覆盖 `2504.19162v2 -> ARXIV:2504.19162`。
- 这两项是前置兼容修复，不改变“中文日志”主目标；但如果不修，live smoke 结果会被已知 API 适配错误污染。

## 验收标准

- `CITE_ANALYZER_RUNTIME_LOG=brief` 运行正式 analyzer 时，每个阶段至少有中文 `START` / `DONE` 或 `SKIP`。
- `CITE_ANALYZER_RUNTIME_LOG=detail` 运行正式 analyzer 时，能看到 Semantic Scholar、OpenAlex、GROBID、全文获取、情感分类的关键中文过程说明。
- `arXiv:2504.19162` 的 live smoke 日志包含中文摘要字段：施引文献、作者画像、全文获取、GROBID 命中、情感分布、报告路径；不硬断言实时数量必须等于历史测试的 3 / 36 / 3。
- fake 0 施引样本的日志明确说明“Semantic Scholar 当前返回 0 篇施引文献，因此跳过下游分析”。
- 0 施引正式 analyzer 运行不能因为空 `citing_papers` 在 stage4/5/6/7 抛错；最终 `status=report_generated`，`report_artifact.export_paths["html"]` 和 `["json"]` 指向已生成文件，并包含空作者画像、空情感摘要和可读的 0 施引结果。
- OpenAlex 单作者 TLS / URL 错误输出为 `WARN`，并包含 `impact=single_author`，不会被描述成全流程失败。
- GROBID 未命中输出为 `WARN` 或 `DETAIL`，并说明已降级到文本/LLM 定位。
- Semantic Scholar 默认字段不再包含 `authors.name` / `citingPaper.authors.name`。
- arXiv 版本号输入和 resolver 回填都不会把 `vN` 版本号传入 Semantic Scholar `ARXIV:` 查询。
- 任何日志不得包含 `SEMANTIC_SCHOLAR_API_KEY` 的值、`x-api-key` header 值或完整 `.env` 内容。
- contract 测试只断言稳定 token 和少量关键中文短语，不依赖 emoji。
- `brief` 输出不超过每个目标约 30 行；`detail` 可以更长，但必须按阶段分段。
- 目标级摘要块字段顺序固定为：目标论文、施引文献、作者画像、全文获取、GROBID命中、引用情感、降级说明、报告路径 / 下一步建议。

## 验证计划

基础验证：

- `python scripts/test_agent/run_contract.py`
- `python scripts/test_agent/check_project_contract.py`
- `python scripts/test_agent/run.py --log brief`
- `python scripts/test_agent/run.py --log detail`

这些命令只验证测试 `StageLogger` 回归，不证明正式 RuntimeLogger 生效。

RuntimeLogger 稳定 contract：

- `python scripts/test_agent/runtime_logging_contract.py`

运行日志验证：

- 新增并运行：`python scripts/test_agent/e2e_real_smoke.py --target https://arxiv.org/abs/2504.19162 --max-citations 3 --log detail`
- PowerShell 环境变量等价入口：`$env:CITE_ANALYZER_RUNTIME_LOG="detail"; python scripts/test_agent/e2e_real_smoke.py --target https://arxiv.org/abs/2504.19162 --max-citations 3`

可选人工观察：

- 如果需要观察真实 0 施引路径，可手动运行 `python scripts/test_agent/e2e_real_smoke.py --target https://arxiv.org/abs/2602.04144 --max-citations 3 --log detail`。
- 该命令不作为固定验收，因为外部数据库可能随时间返回非 0 施引或触发 429。

关键断言：

- 输出包含 `阶段2 | 抓取施引文献`。
- 输出包含 `GROBID` 和 `命中` 或 `未命中`。
- 输出包含 `引用情感` 和 `报告路径`。
- 输出不包含 API key 前缀或完整密钥。
- 对 live smoke 只断言摘要字段和日志语义，不断言实时施引数量必须固定。

0 施引断言只属于 `runtime_logging_contract.py`：

- 输出包含 `Semantic Scholar 当前返回 0 篇施引文献`。
- 输出包含 `SKIP`。
- 最终 `status=report_generated`，HTML / JSON 路径存在。

## 风险与缓解

- 风险：中文自由文本难以稳定测试。
  - 缓解：测试只锁定 token、阶段名和少量固定短语，动态数值用正则或结构化字段检查。

- 风险：日志过于详细，掩盖真正错误。
  - 缓解：默认 `brief`；detail 分段；`FAIL` 仍保留原始 traceback 或异常摘要。

- 风险：runtime logger 与测试 `StageLogger` 语义漂移。
  - 缓解：先共享 token 词汇表和模式名；后续如重复明显再抽 formatter。

- 风险：外部 API 不稳定导致 smoke 偶发失败。
  - 缓解：live smoke 和 contract 分层；contract 用 fake client，live smoke 单独运行并输出外部依赖状态；live smoke 不并入默认 `run.py` / `check-project.sh`。

- 风险：0 施引被误当作错误，导致流程仍在下游节点崩溃。
  - 缓解：将 no-op 下游状态填充列为验收标准，并用 fake-client contract 验证。

- 风险：限速日志本身引发误解。
  - 缓解：detail 模式明确写“遵守每秒最多 1 次请求限制”，并输出等待秒数。

- 风险：日志泄露密钥。
  - 缓解：RuntimeLogger 默认过滤 key、token、authorization、x-api-key、secret 等字段；增加专门断言。

- 风险：`contextvars` logger 在未来并发服务中被误用。
  - 缓解：本轮仅承诺本地单次分析；入口必须 `try/finally reset`；如接入常驻服务，必须在请求入口重新配置 contextvar，并增加并发隔离测试。

- 风险：live smoke 被实时施引数量变化误判为失败。
  - 缓解：live smoke 只验证摘要字段和日志语义，不硬编码历史测试数量。

- 风险：`--max-citations` 参数只存在于 smoke 脚本但没有传到 stage2。
  - 缓解：新增 runtime-only options，并让 `fetch_citation_candidates_node` 从 options 读取 `max_citations`。

## 需要用户决定的问题

- `brief` 模式是否保留 emoji。我的建议是保留少量 emoji，因为用户已明确希望用 emoji 和分段提升可读性，但测试不依赖 emoji。
- 是否需要把详细日志同时落盘到 `generated-reports/<target>/run.log`。我的建议是暂不做，先把 stdout 体验做好。

## 建议执行顺序

1. 前置修复 Semantic Scholar 字段兼容：`authors.name` / `citingPaper.authors.name` 改为 `authors` / `citingPaper.authors`，并加 contract。
2. 前置修复 arXiv ID 版本号归一化：在 Semantic Scholar client 边界归一化 `vN`，并加 contract。
3. 实现 `RuntimeLogger`、no-op logger、敏感字段过滤、runtime context helper 和 `AnalysisRuntimeOptions`。
4. 在 analyzer 节点实现 0 施引 no-op 下游状态填充，保证 0 施引样本可正常生成报告。
5. 接入 analyzer 阶段边界日志，覆盖 stage1/2/4/5/6/7 的开始、完成、跳过和失败 re-raise。
6. 接入外部 API detail / warn 日志，覆盖 Resolver、Semantic Scholar、OpenAlex、Fulltext、GROBID。
7. 增加真实样本 smoke 和 contract 断言。
8. 同步 `README.md`、`docs/testing/stage-validation.md`、必要 history。
9. 默认执行基础验证、RuntimeLogger contract 和 `2504.19162` opt-in live smoke；`2602.04144` live smoke 只作按需人工观察，不作为默认执行项或验收项。

## ADR

### Decision

采用“测试 StageLogger 保留，正式 RuntimeLogger 新增”的双层日志方案，并共享稳定 token 与 `brief/detail` 语义。

### Drivers

- 用户需要中文可读日志，而不仅是机器 token。
- 正式 analyzer 链路和测试脚本职责不同，不能把测试 logger 直接塞进业务包。
- 真实外部依赖存在限速、TLS、GROBID 命中率等可恢复问题，日志必须解释影响范围。

### Alternatives considered

- 直接把 `scripts/test_agent/stage_logging.py` 移到 `packages/shared`。
  - 拒绝原因：测试脚本的 `PASS` 语义不适合正式运行链路，迁移会扩大耦合。

- 只改测试脚本输出中文。
  - 拒绝原因：用户当前关心的是正式跑两篇 arXiv 的全流程解释，测试日志不足以覆盖 OpenAlex / GROBID / Semantic Scholar live 行为。

- 只打印 `SKIP` 但不改变空输入控制流。
  - 拒绝原因：当前 graph 无条件串行，空 `citing_papers` 会在 stage4/5/6/7 抛错；必须同时填充空 state 才能正常收口。

- 把 Semantic Scholar 字段兼容和 arXiv 版本号继续作为条件 gate。
  - 拒绝原因：`authors.name` 已知会被官方 API 拒绝，arXiv 版本号也会污染 `ARXIV:` 查询；继续延后会让 live smoke 被已知适配错误干扰。

- 让 live smoke 硬断言 `2504.19162=3`、`2602.04144=0`。
  - 拒绝原因：外部数据库和 API 配额是时变的；live smoke 只应验证日志语义、摘要字段和限速行为。

- 引入第三方 rich logging。
  - 拒绝原因：当前仓库约束不新增依赖，且 Windows / CI 兼容性优先。

### Consequences

- 短期会存在两个 logger，但职责清晰。
- 后续如果日志事件持续增多，可以抽出共享 formatter 或 JSONL sink。
- 需要新增测试防止中文文本频繁变更导致 contract 脆弱。
- 本计划不再只是 formatter 改造，还包含必要的控制流、runtime options 和外部 API 兼容前置修复；执行时应保持这些切片小而可回滚。

### Follow-ups

- 评估是否将最终目标摘要写入报告目录。
- 评估是否增加 JSONL 机器日志用于 CI artifact。
- 评估是否把 OpenAlex / Semantic Scholar 请求统计写入报告 provenance。

## 审查状态

- 初稿：2026-05-16
- Critic 审查：两次 `VERDICT: REVISE`，已按必须修改项补充 0 施引控制流、logger 传递机制、runtime smoke 交付、fake/fixture 稳定验证、stage5/service 落点和 bugfix gate。
- Architect 讨论：`REVISE`，已补充 `ContextVar` set/reset 与 fail re-raise、0 施引非 error 语义、live smoke opt-in、Semantic Scholar / arXiv 前置修复、runtime-only `max_citations` 通路、resolver 日志边界、live smoke 语义 gate。
- 最终状态：待复审
