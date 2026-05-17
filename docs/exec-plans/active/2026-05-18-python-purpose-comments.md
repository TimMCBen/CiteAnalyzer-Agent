# 2026-05-18 Python 用途注释规则与补全计划

## 需求摘要

用户希望给仓库 Python 代码补注释，但注释只说明“每个文件是干什么的、每个函数或类是干什么的”，不解释逐行实现细节。本轮只做计划，不执行源码注释补全。计划必须形成规则文件，并经过多个智能体讨论。

当前代码面事实：

- `apps/`、`packages/`、`scripts/` 下约 74 个 Python 文件。
- 约 85 个类、508 个函数/方法。
- 其中包含大量私有 helper、方法、嵌套局部函数和 `scripts/test_agent/assert_*` 验证函数。
- 当前模块 docstring 只有少量存在，函数/方法 docstring 基本缺失。
- 未跟踪目录 `logs/` 和 `Thesis_Crawling_and_Filtering_System/` 不属于本计划范围。

## 范围

纳入范围：

- `apps/**/*.py`
- `packages/**/*.py`
- `scripts/eval/**/*.py`
- `scripts/test_agent/**/*.py`
- `scripts/*.py` 中属于当前项目验证/运行入口的文件

排除范围：

- `Thesis_Crawling_and_Filtering_System/`
- `logs/`
- `downloaded-papers/`
- `generated-reports/`
- `external/`
- `__pycache__/`
- 任何生成文件、缓存文件、真实 API 输出日志

## 设计原则

1. 注释只写“用途/职责/边界”，不复述代码怎么执行。
2. 优先使用 Python docstring，不新增散落的行内注释。
3. 源码 docstring 默认英文 ASCII；规则文件、计划、history 可中文。
4. 不做语法树层面的 blanket all；按覆盖矩阵定义哪些函数/方法必须写、哪些默认豁免。
5. 规则文件和 AST 检测脚本是硬前置；没有规则和检测，不开始批量补注释。
6. 不引入新依赖，不改变运行行为。
7. 分批执行，避免一次 500+ 函数的大 diff 失控。

## 长期规则文件

新增：

- `docs/CODE_COMMENTING_RULES.md`

内容必须包含：

- 模块 docstring 规则：文件顶部 1-2 句，说明该文件在系统中的职责。
- 类 docstring 规则：1 句说明这个类表示的领域对象、客户端、服务、状态或测试 fake。
- 函数/方法 docstring 规则：1-2 句说明函数要完成的任务、关键输入输出或副作用。
- 覆盖矩阵：明确模块、类、顶层函数、方法、私有 helper、嵌套局部函数、测试断言函数、dunder/accessor 的处理方式。
- 防噪音约束：不复述函数名，不复述类型，不写逐行逻辑，不写无信息模板句。
- 语言规则：Python 源码 docstring 默认英文 ASCII；文档可中文。
- 好坏示例。

推荐好例子：

```python
"""Resolve a user paper query into target metadata used by later stages."""
```

推荐坏例子：

```python
"""This function calls normalize, then sets x, then returns y."""
```

## 覆盖矩阵

| 对象 | 默认规则 | 理由 |
|---|---|---|
| 模块文件 | 必须有模块 docstring | 文件职责是用户要求的核心目标 |
| 非空 `__init__.py` | 写一句导出/包职责 | 当前仓库已有类似好例子 |
| 空 `__init__.py` | 可豁免或补一句最短包说明 | 避免无意义注释 |
| 类 / dataclass / Protocol | 必须有类 docstring | 类级说明比字段逐个复述更有价值 |
| Protocol 方法 stub | 默认豁免 | 协议职责由 Protocol 类 docstring 说明 |
| 公共顶层函数 | 必须有 docstring | 稳定调用边界 |
| 公共方法 | 必须有 docstring，除非明显 accessor/dunder | 方法是类的主要行为边界 |
| 生产代码私有 helper | 非显然 helper 必须有 docstring | 说明隐藏决策点；明显一行 helper 可豁免 |
| `@property` / 明显 accessor | 默认豁免 | 名字和返回值通常足够，强制会重复 |
| 普通 dunder 方法 | 默认豁免 | 协议语义已固定；类 docstring 覆盖整体用途 |
| 嵌套局部函数 | 默认豁免 | 常是局部 glue/fake/callback；复杂时应优先提到顶层或在外层说明 |
| `scripts/test_agent/assert_*` | 默认豁免 | 函数名已表达验证点，强制易复述 assert |
| 测试 fake/stub 类 | 类 docstring 必须有 | 说明 fake 模拟哪个依赖 |
| 测试 fake/stub 函数 | 默认豁免，复杂 fake 可补 | 防止测试脚本噪音过高 |

执行时必须把该矩阵落实到 `comment_contract.py`，不能靠人工记忆。

## RALPLAN-DR 摘要

### Principles

- 只说明职责，不解释实现。
- 规则先行，执行跟随规则。
- 覆盖口径可机器检查。
- 小批量、可回滚、可审查。
- 不改变运行行为。

### Decision Drivers

- 可读性：让后来的人和 Agent 快速知道文件/类/函数职责。
- 低噪音：避免为了覆盖率制造无意义注释。
- 可验证：用 AST contract 按覆盖矩阵检查缺失项和豁免项。

### Options

Option A：按语法树“所有 FunctionDef/ClassDef/Module”硬覆盖。

- Pros：规则最简单。
- Cons：会强迫嵌套局部函数、Protocol stub、明显 accessor、测试断言 wrapper 写低信号 docstring。
- 结论：拒绝。

Option B：规则文件 + 覆盖矩阵 + AST 检测 + 分批补注释。

- Pros：质量可控，能逐批验证，防止噪音注释。
- Cons：检测脚本更复杂，执行周期稍长。
- 结论：采用。

Option C：只补公共边界，不做检测脚本。

- Pros：最少改动。
- Cons：无法证明覆盖目标，后续容易退化。
- 结论：拒绝。

## 实施步骤

### 第 1 步：新增规则文件与检测脚本（硬前置）

新增：

- `docs/CODE_COMMENTING_RULES.md`
- `scripts/test_agent/comment_contract.py`

检测脚本要求：

- 用 `ast` 扫描纳入范围内的 Python 文件。
- 按覆盖矩阵输出三类结果：`required`、`exempt`、`skipped_by_wave`。
- 输出 `missing` 明细和统计。
- 支持 `--report-only`，用于建立 baseline，不阻塞。
- 支持 `--scope` 或路径参数，用于分批验证。
- 支持最终严格模式，要求当前 scope 内 `missing=0`。
- 不访问网络，不新增依赖。

第一批提交只包含规则文件和检测脚本，不补业务源码注释。

验收：

- `docs/CODE_COMMENTING_RULES.md` 明确覆盖矩阵和防噪音规则。
- `comment_contract.py --report-only` 能输出当前 baseline。
- `python -m compileall apps packages scripts` 通过。
- 不接入 `scripts/test_agent/run.py`，直到补注释批次完成并严格模式通过。

### 第 2 步：第一批补核心边界

范围：

- `packages/shared/**/*.py`
- `apps/analyzer/**/*.py`
- 各包 `__init__.py`
- `packages/citation_sources/**/*.py`

重点：

- 模块职责。
- 关键入口函数职责。
- 数据模型/协议/客户端类职责。
- 非显然私有 helper 职责。

验证：

- `D:\ProgramData\Anaconda3\python.exe -m compileall apps packages scripts`
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/comment_contract.py --scope core`
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/run.py`
- 记录 before/after docstring 统计。

### 第 3 步：第二批补分析能力模块

范围：

- `packages/author_intel/**/*.py`
- `packages/paper_identity/**/*.py`
- `packages/sentiment/**/*.py`

重点：

- 外部客户端说明数据源和返回的标准化对象。
- 规则函数说明判定目的，不展开阈值细节。
- LLM prompt 相关函数说明“构造复核请求/解析结构化输出”，不重复 prompt。
- Workflow 内部嵌套节点函数默认豁免；如职责复杂，在外层 workflow docstring 中说明阶段结构。

验证：

- `compileall`
- `scripts/test_agent/paper_identity.py`
- `scripts/test_agent/stage4.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `scripts/test_agent/comment_contract.py --scope analysis`
- 记录 before/after docstring 统计。

### 第 4 步：第三批补报告与评估脚本

范围：

- `packages/reporting/**/*.py`
- `scripts/eval/**/*.py`

重点：

- 报告生成函数说明产物职责。
- PDF/HTML helper 中明显一行格式化函数可豁免；非显然 layout/aggregation helper 要说明用途。
- 评估脚本入口说明输入 JSONL、输出预测或指标。

验证：

- `compileall`
- `scripts/test_agent/stage7.py`
- `scripts/test_agent/comment_contract.py --scope reporting-eval`
- 构造临时 JSONL 跑 `scripts/eval/paper_identity_score.py`
- 记录 before/after docstring 统计。

### 第 5 步：第四批补测试脚本并接入聚合入口

范围：

- `scripts/test_agent/**/*.py`

重点：

- 模块 docstring 说明该脚本验证哪个 stage/contract。
- `main()` 可写统一用途说明。
- `assert_*` 默认豁免；只有复杂跨阶段断言才补一句 contract 说明。
- fake/stub class 必须说明模拟对象。

完成后：

- 把 `comment_contract.py` 接入 `scripts/test_agent/run.py`。
- 更新 `docs/testing/stage-validation.md`。
- 更新 `docs/QUALITY_SCORE.md`。
- 如执行中实际改动代码，新增或更新 `docs/histories/2026-05/...`。

验证：

- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/comment_contract.py`
- `D:\ProgramData\Anaconda3\python.exe -m compileall apps packages scripts`
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/run.py`
- `git diff --check`
- 记录 before/after docstring 统计。

## 验收标准

- `docs/CODE_COMMENTING_RULES.md` 存在，并说明模块/类/函数用途注释规则、覆盖矩阵和防噪音约束。
- `scripts/test_agent/comment_contract.py` 存在，并能输出 `required/exempt/skipped_by_wave/missing`。
- 最终严格模式下，纳入范围的模块 docstring 覆盖率为 100%。
- 最终严格模式下，纳入范围的类 docstring 覆盖率为 100%。
- 最终严格模式下，覆盖矩阵要求的顶层函数、公共方法、非显然私有 helper docstring 覆盖率为 100%。
- 豁免对象必须在脚本统计或明细中可见，不能静默遗漏。
- `D:\ProgramData\Anaconda3\python.exe -m compileall apps packages scripts` 通过。
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/run.py` 通过。
- 注释不改变运行逻辑。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 注释变成实现复述 | 代码噪音增加 | 规则文件明确禁止，review 抽样检查 |
| 语法树 blanket all | 大量低信号 docstring | 覆盖矩阵豁免嵌套函数、Protocol stub、accessor、测试 assert |
| 分批被全仓 gate 卡死 | 无法逐步提交 | `comment_contract.py` 支持 scope 与 `skipped_by_wave` |
| 一次性 diff 太大 | 难审查、难回滚 | 按架构边界分 4 批 |
| 非 ASCII 注释进入源码 | 风格不统一 | 源码 docstring 默认英文 ASCII |
| 检测脚本误报 | 阻塞开发 | 输出 exempt 明细，必要时用带理由 allowlist |

## 多智能体审查状态

已请求两个智能体审查：

- `critic`：结论 `REVISE`。主要意见是必须定义覆盖矩阵，测试 `assert_*`、嵌套 helper、局部 fake 默认不应强制 docstring；验收要增加 `compileall`、`excluded` 明细和 before/after 统计。
- `architect`：结论 `REVISE`。主要意见是不能字面“所有函数”；规则文件位置 `docs/CODE_COMMENTING_RULES.md` 合理，但执行计划应落到 `docs/exec-plans/active/`；验证应以 `scripts/test_agent/run.py` 和 `scripts/check-project.sh` 为主 gate，`compileall` 是语法补充。

本版已合并上述意见。

## ADR

### Decision

采用“规则文件 + 覆盖矩阵 + AST 检测 + 分批补 docstring”的方案。

### Drivers

- 用户要求覆盖文件、函数和类的用途说明。
- 当前 docstring 覆盖率低，需要机器检查防止遗漏。
- 仓库内存在大量测试断言、嵌套函数、accessor 和 helper，不能用 blanket all 规则。
- 任务规模较大，必须分批降低审查风险。

### Alternatives considered

- 按语法树全量硬覆盖：拒绝，噪音太高。
- 只补公共边界不做检测：拒绝，不可验证。
- 只写外部文档不改源码：拒绝，无法在阅读代码时直接看到职责。

### Why chosen

规则先行能统一风格；覆盖矩阵能避免噪音；AST 检测能让目标可验证；分批执行能降低回归和审查成本。

### Consequences

- 检测脚本比简单 docstring checker 更复杂。
- 后续新增 Python 文件/函数时需要遵守规则。
- 需要维护少量有理由的豁免。

### Follow-ups

- 执行前先创建 `docs/CODE_COMMENTING_RULES.md` 与 `scripts/test_agent/comment_contract.py`。
- 将本计划同步到 `docs/exec-plans/active/2026-05-18-python-purpose-comments.md`。
- 执行后考虑在 CI 或 `scripts/test_agent/run.py` 中接入最终严格模式。

## 执行交接建议

### Ralph 单智能体路径

适合逐批执行。建议 `$ralph` 按本计划逐批改，每批运行对应验证后提交。

### Team 多智能体路径

适合并行执行，但必须先完成规则文件和检测脚本。建议分工：

- `executor`：规则文件 + AST 检测脚本。
- `executor`：`packages/shared` + `apps/analyzer` + `packages/citation_sources`。
- `executor`：`packages/author_intel` + `packages/paper_identity` + `packages/sentiment`。
- `executor`：`packages/reporting` + `scripts/eval`。
- `test-engineer`：测试脚本 docstring + 聚合验证。
- `code-reviewer`：抽样检查注释是否只说明用途。

团队验证路径：

- 每个 lane 跑 scoped `comment_contract.py --scope ...` 和 `compileall`。
- 最后统一跑 `scripts/test_agent/comment_contract.py` 和 `scripts/test_agent/run.py`。
- code-reviewer 必须确认没有把实现细节写进 docstring。
