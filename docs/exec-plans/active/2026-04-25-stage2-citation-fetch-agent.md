# 阶段 2 执行计划：文献爬取智能体细化

## 目标

把 MVP 主计划中的“阶段 2：文献爬取智能体”细化成一份可独立推进的执行计划。最终目标是让 `文献爬取智能体` 在阶段 1 已输出的目标论文标准化线索基础上，完成主链路施引文献抓取、多源融合、去重与来源保留，并把结果稳定交还给总智能体状态。

## 范围

- 包含：
  - 定义阶段 2 的共享数据对象与状态边界
  - 明确 `Semantic Scholar` 与 `Crossref` 在主链路中的角色分工
  - 规划 `packages/citation-sources/` 的目录与模块职责
  - 设计抓取、标准化、合并、去重、来源追踪的执行切片
  - 规划阶段 2 的脚本验证与降级验证
- 不包含：
  - `Google Scholar` 补充源接入实现
  - 学者识别、情感分析、报告生成
  - 真实前端交互
  - 生产级缓存、队列与持久化

## 背景

- 父计划：
  - `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- 相关文档：
  - `docs/ARCHITECTURE.md`
  - `docs/product-specs/citation-analysis-mvp.md`
  - `docs/testing/stage-validation.md`
- 相关代码路径：
  - `apps/analyzer/`
  - `packages/shared/`
- 已知约束：
  - 阶段 2 依赖阶段 1 已完成的 `AnalysisState` / `TargetPaper`
  - 主链路只依赖 `Semantic Scholar + Crossref`
  - `Google Scholar` 放到阶段 3 单独评估
  - 需要保留来源信息，不能只留下合并后的“干净结果”
  - 验证入口应最终落到 `scripts/test_agent/stage2.py`

## 阶段目标拆解

### 目标 A：把阶段 2 的输入输出边界定死

需要先明确三件事：

1. `文献爬取智能体` 消费什么输入
2. 它向总智能体回传什么结构
3. 哪些失败属于“局部失败可降级”，哪些属于“主链路失败”

建议最小输入：

- `target_paper.canonical_id`
- `target_paper.doi`
- `target_paper.source_ids`
- 可选抓取参数：
  - `max_results`
  - `preferred_sources`
  - `allow_partial`

建议最小输出：

- `citing_papers`
- `source_trace`
- `fetch_summary`
- `errors`

### 目标 B：把主链路拆成可独立实现的切片

阶段 2 不应一次性实现成大函数，建议拆成以下切片：

1. 目标论文标识解析与查询计划生成
2. `Semantic Scholar` 抓取
3. `Crossref` 抓取
4. 来源字段标准化
5. 多源记录合并与去重
6. 来源追踪与统计摘要
7. 接回总智能体状态

### 目标 C：保证阶段 2 有独立验证闭环

除了最终接入总图，还要能单独回答：

- 对固定目标论文，抓到多少条候选施引记录
- 去重后还剩多少条
- 每条记录来自哪些源
- 当单一来源失败时，是否还能交付部分结果

## 共享数据设计

### `CitingPaper`

建议最小字段：

- `canonical_id`
- `title`
- `doi`
- `year`
- `authors`
- `venue`
- `abstract`
- `source_links`
- `source_names`
- `source_specific_ids`

说明：

- `source_names` 用于快速判断该记录由哪些来源命中
- `source_specific_ids` 用于保存 `Semantic Scholar Corpus ID`、`Crossref DOI` 等来源内标识
- `abstract` 第一版可选；如果来源缺失，不阻塞本阶段交付

### `SourceTrace`

建议作为单独对象，而不是把所有来源信息硬塞进 `CitingPaper`：

- `candidate_id`
- `source_name`
- `source_record_id`
- `query_used`
- `fetched_at`
- `raw_title`
- `raw_doi`
- `merge_status`

作用：

- 方便排查“这条记录为什么会被合并/丢弃”
- 为阶段 7 的联调与问题回溯提供依据

### `FetchSummary`

建议保留汇总对象：

- `target_query`
- `semantic_scholar_candidates`
- `crossref_candidates`
- `merged_candidates`
- `deduped_candidates`
- `partial_failure`
- `notes`

## 代码落点建议

建议新增目录：

- `packages/citation-sources/__init__.py`
- `packages/citation-sources/models.py`
- `packages/citation-sources/clients/semantic_scholar.py`
- `packages/citation-sources/clients/crossref.py`
- `packages/citation-sources/normalize.py`
- `packages/citation-sources/dedupe.py`
- `packages/citation-sources/service.py`

职责划分：

- `models.py`
  - 阶段 2 领域对象
- `clients/*`
  - 外部 API 访问与原始响应适配
- `normalize.py`
  - 不同来源到统一字段的映射
- `dedupe.py`
  - 去重和合并策略
- `service.py`
  - 对外暴露给总智能体调用的抓取入口

## 主链路策略

### 查询优先级

建议优先级：

1. DOI
2. 已知来源 ID
3. 标题

原因：

- DOI 最稳定，歧义最小
- 来源 ID 适合补查与校验
- 标题召回高但噪声也高，应作为补充查询

### 来源分工

`Semantic Scholar`

- 优先承担施引关系查询
- 优先返回候选施引论文主体

`Crossref`

- 优先承担 DOI / 元数据补全
- 不假设一定能独立提供完整施引列表

这里的关键判断是：阶段 2 的“施引关系”主语义优先落在 `Semantic Scholar`，`Crossref` 更像补足元数据和交叉校验源，而不是与前者完全对等的召回源。

### 去重策略

建议按三层顺序：

1. DOI 完全匹配
2. 标题规范化后完全匹配
3. `title + year + first_author` 弱匹配

规则：

- 强匹配直接合并
- 弱匹配只在来源不足时启用，并记录 `merge_status = heuristic`
- 无法确认时宁可保留两条候选，也不要过度误合并

## 失败与降级策略

### 可降级场景

- `Crossref` 请求失败，但 `Semantic Scholar` 成功
- 某些记录缺 DOI 或摘要
- 部分记录作者字段不完整

处理方式：

- 标记 `partial_failure = true`
- 返回已获取结果
- 在 `fetch_summary.notes` 记录缺口

### 不可静默吞掉的失败

- 目标论文标识无法生成有效查询
- `Semantic Scholar` 和 `Crossref` 全部失败且无结果
- 返回结果结构不满足最小输出契约

处理方式：

- 向总智能体显式返回错误
- 由总智能体决定是否中止后续阶段

## 实现切片

### 切片 1：阶段对象与接口

- 定义 `CitingPaper` / `SourceTrace` / `FetchSummary`
- 明确服务入口函数签名
- 明确与 `AnalysisState` 的挂接字段

完成标准：

- 不接外部 API，也能通过静态样例构造完整输出对象

### 切片 2：`Semantic Scholar` 客户端

- 封装请求参数
- 处理分页或数量限制
- 适配原始响应到内部中间结构

完成标准：

- 能用固定样本论文拉到候选施引记录

### 切片 3：`Crossref` 客户端

- 拉取 DOI 与补充元数据
- 定义失败时的降级路径

完成标准：

- 能对已有候选记录补全一部分字段

### 切片 4：标准化与去重

- 统一标题、DOI、作者字段
- 实现强匹配与弱匹配
- 输出合并前后数量

完成标准：

- 给定两组样例数据，能产出去重后的统一清单

### 切片 5：总智能体集成

- 将文献爬取结果写回状态
- 暴露给后续阶段消费

完成标准：

- 阶段 1 输出可直接衔接阶段 2 服务入口

### 切片 6：阶段脚本验证

- 实现 `scripts/test_agent/stage2.py`
- 固定一篇样本论文
- 打印并断言关键统计

完成标准：

- 本地可独立运行
- 失败时能指出是抓取失败、标准化失败还是去重失败

## 验证方式

- 命令：
  - `bash ./scripts/check-project.sh`
  - `python ./scripts/test_agent/stage2.py`
  - 后续如需要，再补 API mock 或 fixture 驱动的验证命令
- 手工检查：
  - 给定目标论文后，能够输出非空施引候选
  - 合并后记录数小于等于原候选总数
  - 任意一条合并结果能追溯回来源
  - 单来源失败时仍能返回部分结果并暴露缺口
- 观测检查：
  - 记录每个来源的请求状态码 / 错误摘要
  - 记录合并前数量、去重后数量
  - 记录强匹配 / 弱匹配命中数
  - 记录最终返回是否为 `partial_failure`

## 里程碑

1. 数据对象和服务边界冻结
2. `Semantic Scholar` 主抓取链路跑通
3. `Crossref` 补全链路跑通
4. 标准化、去重和来源追踪跑通
5. 阶段 2 脚本验证完成
6. 与总智能体状态图完成一次联调

## 进度记录

- [x] 新建阶段 2 细化执行计划
- [x] 定义 `CitingPaper` / `SourceTrace` / `FetchSummary`
- [x] 明确阶段 2 服务入口与状态挂接点
- [x] 设计 `Semantic Scholar` 主抓取参数与输出映射
- [x] 设计 `Crossref` 补全参数与输出映射
- [x] 明确去重规则与来源追踪规则
- [x] 规划 `packages/citation-sources/` 模块边界
- [x] 规划 `scripts/test_agent/stage2.py` 的验证样例与断言点
- [x] 将阶段 2 计划与父计划建立引用关系

## 当前实现状态

已完成的最小实现：

- `packages/citation_sources/models.py`
- `packages/citation_sources/normalize.py`
- `packages/citation_sources/dedupe.py`
- `packages/citation_sources/service.py`
- `packages/citation_sources/clients/semantic_scholar.py`
- `packages/citation_sources/clients/crossref.py`
- `apps/analyzer/graph.py`
- `apps/analyzer/nodes.py`
- `apps/analyzer/main.py`
- `scripts/test_agent/stage2.py`

当前阶段 2 已具备：

- 统一领域对象
- 多源记录标准化
- 基于 DOI / 标题+年份+首作者 的去重合并
- 来源追踪输出
- 单来源失败时的 `partial_failure` 降级
- 真实 `Semantic Scholar` Graph API 客户端
- 真实 `Crossref` metadata enrichment 客户端
- 阶段 2 graph 节点和 `run_stage2_analysis()` 入口
- 可选 live smoke 验证开关

尚未完成：

- 基于真实样本论文的在线抓取验证
- 更细的 rate limit / backoff 观测与日志
- 把阶段 2 接入默认分析主路径而不影响阶段 1 验证

## 决策记录

- 2026-04-25：阶段 2 细化计划单独开文档，不继续在主 MVP 计划中堆实现细节，以保持父计划可读性。
- 2026-04-25：阶段 2 主链路优先以 `Semantic Scholar` 承担施引关系查询，`Crossref` 主要承担元数据补全与交叉校验。
- 2026-04-25：来源追踪单独建模，不只保留合并后的 `CitingPaper`，以支持后续联调和问题回溯。
