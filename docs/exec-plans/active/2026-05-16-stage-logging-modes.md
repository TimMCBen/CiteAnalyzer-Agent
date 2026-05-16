# 阶段日志模式执行计划

## 目标

为 `scripts/test_agent/` 下的阶段验证入口增加统一日志模式，让用户运行时可以选择：

- 简略日志：只输出阶段开始 / 通过 / 跳过 / 失败等摘要，适合日常验证。
- 详细日志：输出每个阶段的关键输入、断言点、产物路径、降级信息和可选 live smoke 状态，适合调试。

该能力应覆盖聚合入口 `scripts/test_agent/run.py` 和单阶段入口，不改变现有测试断言语义。

## 当前依据

- `scripts/test_agent/run.py:23` 当前直接顺序调用各阶段脚本，尚无 CLI 参数或环境变量透传。
- `scripts/test_agent/run.py:24` 到 `scripts/test_agent/run.py:32` 是聚合入口的阶段调度清单。
- `scripts/test_agent/stage1.py:157` 到 `scripts/test_agent/stage1.py:164` 目前使用散落的 `print("[PASS] ...")` 输出。
- `docs/testing/stage-validation.md:7` 到 `docs/testing/stage-validation.md:9` 当前只记录基础运行入口，没有日志模式说明。
- `docs/testing/stage-validation.md:13` 到 `docs/testing/stage-validation.md:21` 当前列出了聚合阶段脚本清单。
- `scripts/test_agent/run_contract.py` 已验证 `run.py` 聚合脚本清单，日志模式改造需要同步扩展该 contract。

## 范围

包含：

- 新增阶段日志工具模块，例如 `scripts/test_agent/stage_logging.py`。
- 为 `run.py` 增加 `--log brief|detail` 参数，并通过环境变量传给子阶段。
- 支持项目级入口通过环境变量选择日志模式，例如 `CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`。
- 支持单阶段脚本通过 `CITE_ANALYZER_STAGE_LOG=brief|detail` 控制日志。
- 将阶段脚本的核心输出迁移到统一 logger，至少覆盖 `import_contract.py`、`stage1.py`、`stage2.py`、`stage3.py`、`stage4.py`、`stage5.py`、`stage6.py`、`stage56_integration.py`、`stage7.py`、`stage8.py`、`e2e_mvp.py`。
- 将验证契约脚本的核心输出迁移到统一 logger，至少覆盖 `run_contract.py` 和 `check_project_contract.py`，但这两个脚本不纳入 `run.py` 聚合清单。
- 更新 README 和 `docs/testing/stage-validation.md` 的运行说明。
- 增加或扩展 contract 测试，证明日志模式参数、环境变量透传和详细日志输出存在。

不包含：

- 引入第三方日志依赖。
- 改造业务包 `apps/` / `packages/` 的内部 logging。
- 把详细日志写入持久日志文件，除非后续另开计划。
- 改变阶段断言、live smoke 开关或现有 fixture 行为。

## 日志契约

### 模式

- `brief`：默认模式。输出阶段开始、关键 PASS、最终通过、TODO 阶段提示和失败摘要。
- `detail`：在 `brief` 基础上额外输出上下文细节。

### 入口

- 聚合入口：`python scripts/test_agent/run.py --log brief`
- 聚合详细：`python scripts/test_agent/run.py --log detail`
- 项目级入口：`bash ./scripts/check-project.sh`
- 项目级详细：`CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`
- 单阶段详细：`CITE_ANALYZER_STAGE_LOG=detail python scripts/test_agent/stage6.py`
- Windows PowerShell 单阶段详细：`$env:CITE_ANALYZER_STAGE_LOG="detail"; python scripts/test_agent/stage6.py`

优先级约定：

- `run.py --log ...` 优先级高于当前 shell 中已有的 `CITE_ANALYZER_STAGE_LOG`。
- `check-project.sh` 不新增 CLI 参数，只透传调用环境中的 `CITE_ANALYZER_STAGE_LOG`。
- 单阶段脚本只读取 `CITE_ANALYZER_STAGE_LOG`。
- 缺省值为 `brief`。
- 非法日志模式必须快速失败，错误信息列出允许值 `brief` / `detail`，不要静默回退。

### 父子职责与失败契约

- `run.py` 负责聚合级日志：每个子脚本执行前输出 `START aggregate::<script>`，成功后输出 `DONE aggregate::<script>`。
- 单阶段脚本负责阶段内部日志：用 `PASS <stage>::<case>`、`SKIP <stage>::<case>`、`DONE <stage>` 表达阶段内结果。
- 父子两层允许同时输出 start / done，但命名空间必须不同：父层只使用 `aggregate::<script>`，子层只使用真实阶段名。
- `StageLogger` 不捕获断言异常，不吞 traceback，不改退出码。
- 单阶段脚本内如果显式捕获预期异常进行断言，可以输出 `PASS`；非预期异常不由 logger 包装。
- `run.py` 可以捕获 `subprocess.CalledProcessError` 打印一条 `FAIL aggregate::<script> exit_code=<code>` 摘要，然后必须重新抛出或以同一非零状态退出，保留原始失败证据。
- `brief` 模式必须能看到失败发生在哪个聚合脚本；`detail` 模式不能替代 traceback。

### 建议 API

在 `scripts/test_agent/stage_logging.py` 中提供：

- `get_log_mode() -> Literal["brief", "detail"]`
- `StageLogger(stage_name: str)`
- `logger.start(message: str | None = None)`
- `logger.pass_case(case_name: str, detail: str | None = None)`
- `logger.detail(message: str)`
- `logger.skip(case_name: str, reason: str)`
- `logger.fail(case_name: str, detail: str | None = None)`
- `logger.done(message: str | None = None)`

输出允许使用少量 emoji 和分段符号提升人读可扫性，但必须遵守：

- 不使用 ANSI 彩色控制符，保证 CI、Windows 终端和日志重定向可读。
- emoji 只作为状态前缀，不作为机器判断依据；contract 测试应断言稳定文本 token，例如 `PASS` / `FAIL` / `SKIP` / `DETAIL`。
- brief 模式中 emoji 和分段符号要克制，避免淹没测试结果。
- detail 模式可以使用清晰分段符号，例如 `--- stage6 detail ---` 或 `=== stage6 ===`，但格式由 `stage_logging.py` 统一生成。
- 如果终端无法正常显示 emoji，日志仍应能通过英文状态词和阶段名理解。

### 逐脚本 detail 最小矩阵

| 脚本 | detail 模式至少输出 |
| --- | --- |
| `import_contract.py` | 被保护的可选依赖名、导入目标模块、断言目标符号 |
| `stage1.py` | case 名、输入类型期望、解析出的 `paper_query_type` / `resolve_status` |
| `stage2.py` | live smoke 是否跳过 / 启用、目标 DOI 或 fixture 目标、Semantic Scholar 候选数、Crossref 候选数、合并 / 去重数量、错误摘要 |
| `stage3.py` | TODO / skip 原因、后续对应计划或补充源边界 |
| `stage4.py` | citing paper 数、作者画像数、各类 label 计数、缺失 h-index 路径是否覆盖 |
| `stage5.py` | 样本路径、临时目录、每篇 fixture 的 source type、落盘路径是否存在、live fetch 是否跳过 / 启用 |
| `stage6.py` | 样本路径、上下文总数、各 sentiment label 计数、unknown 数量、source type 分布、real citing5 / GROBID smoke 是否跳过 / 启用 |
| `stage56_integration.py` | 被验证的 analyzer 节点、fixture citing paper 数、写回 state 的 scholar / fulltext / sentiment 字段摘要 |
| `stage7.py` | 临时报告目录、HTML / JSON 路径、报告 summary 中趋势 / 来源 / 学者 / 情感 / 降级区块是否存在 |
| `stage8.py` | TODO / skip 原因；若仍为占位，不进入 `run.py` 聚合清单 |
| `e2e_mvp.py` | stage2 样本路径、总控最终状态、报告产物路径、unknown / partial failure 是否暴露 |
| `run_contract.py` | 聚合脚本清单、`--log` 参数用例、子进程环境变量断言 |
| `check_project_contract.py` | `check-project.sh` 的 Python 选择顺序、路径转换检查、日志环境变量透传检查 |

## 实施步骤

1. 建立统一日志模块
   - 新增 `scripts/test_agent/stage_logging.py`。
   - 实现环境变量解析，并对非法值快速报错。
   - 保持默认 `brief`，避免改变当前普通运行的信息密度。
   - 在统一模块内集中定义状态前缀和分段符号，例如 `▶ START`、`✅ PASS`、`⏭ SKIP`、`❌ FAIL`、`ℹ DETAIL`；脚本不得各自拼装不同风格。

2. 改造聚合入口
   - 在 `scripts/test_agent/run.py` 增加 `argparse` 参数 `--log {brief,detail}`。
   - 子进程调用时复制 `os.environ`，写入 `CITE_ANALYZER_STAGE_LOG`。
   - 为每个子脚本输出聚合级 stage start / done。
   - 子脚本失败时输出聚合级 `FAIL aggregate::<script> exit_code=<code>`，并保持非零退出。
   - 更新 `scripts/test_agent/run_contract.py`，检查默认调度不变，并新增详细模式透传断言。

3. 改造单阶段脚本
   - 优先替换散落 `print("[PASS] ...")` 为 `StageLogger.pass_case(...)`。
   - 按“逐脚本 detail 最小矩阵”补齐每个脚本的 detail 输出。
   - 对 `stage3.py` / `stage8.py` 这类 TODO 脚本使用 `skip` 输出，不伪装成通过。

4. 改造项目级入口契约
   - `scripts/check-project.sh` 保持当前 CLI 形态，不新增参数。
   - 明确支持通过环境变量透传日志模式：`CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`。
   - 扩展 `scripts/test_agent/check_project_contract.py`，验证 `check-project.sh` 不覆盖调用方设置的 `CITE_ANALYZER_STAGE_LOG`。

5. 文档同步
   - 更新 `README.md` 的测试入口说明，增加日志模式示例。
   - 更新 `docs/testing/stage-validation.md`，记录日志模式、环境变量和适用场景。
   - 更新 `docs/testing/README.md`，说明项目级入口仍是 `scripts/check-project.sh`，详细日志通过环境变量开启。
   - 如最终实施改变了验证入口行为，补充 `docs/histories/2026-05/` 记录。

6. 验证与收口
   - 运行 `python scripts/test_agent/run_contract.py`。
   - 运行 `python scripts/test_agent/check_project_contract.py`。
   - 运行 `python scripts/test_agent/run.py --log brief`。
   - 运行 `python scripts/test_agent/run.py --log detail`。
   - 运行 `CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh`。
   - 运行至少一个单阶段详细模式，例如 PowerShell 下 `$env:CITE_ANALYZER_STAGE_LOG="detail"; python scripts/test_agent/stage6.py`。
   - 验证非法模式会失败，例如 `python scripts/test_agent/run.py --log noisy` 或 `CITE_ANALYZER_STAGE_LOG=noisy python scripts/test_agent/stage1.py`。
   - 确认 `stage3.py` / `stage8.py` 仍为 TODO，占位语义不变，且直接运行时输出 `SKIP` / TODO 原因。

## 验收标准

- `python scripts/test_agent/run.py` 默认仍可运行，且聚合脚本清单与当前一致。
- `CITE_ANALYZER_STAGE_LOG=detail bash ./scripts/check-project.sh` 可通过项目级入口开启详细日志。
- `python scripts/test_agent/run.py --log brief` 输出简略摘要，不刷出每个 fixture 的大量上下文。
- `python scripts/test_agent/run.py --log detail` 能看到“逐脚本 detail 最小矩阵”中列出的字段。
- 日志可包含少量 emoji 和分段符号，但机器可测内容必须依赖稳定文本 token，且禁用 ANSI 彩色控制符。
- 任一单阶段脚本可通过 `CITE_ANALYZER_STAGE_LOG=detail` 开启详细日志。
- `run_contract.py` 覆盖 `--log` 参数解析和对子进程环境变量透传。
- `check_project_contract.py` 覆盖 `check-project.sh` 不覆盖调用方日志环境变量。
- 非法日志模式会快速失败，并明确提示允许值。
- 阶段失败时不能被日志封装吞掉；仍要保留 Python traceback 或等价的明确失败证据。
- `stage3.py` / `stage8.py` 作为占位脚本直接运行时输出 `SKIP` / TODO 原因，不进入 `run.py` 聚合清单。
- 文档明确告诉用户什么时候用 brief，什么时候用 detail。
- 不新增第三方依赖，不改变阶段测试的断言结果。

## 风险与缓解

- 风险：详细日志过多导致 CI 输出难读。
  - 缓解：默认保持 `brief`，detail 只在显式开启时输出。
- 风险：emoji 在部分终端或 CI artifact 中显示异常。
  - 缓解：emoji 只做视觉辅助，状态词和阶段名始终以 ASCII 文本输出。
- 风险：每个阶段脚本各写一套日志格式，后续维护困难。
  - 缓解：统一从 `stage_logging.py` 输出，不允许新增散落格式。
- 风险：PowerShell / bash 环境变量写法不同，用户误用。
  - 缓解：README 和测试文档同时给出两种示例。
- 风险：聚合入口改造破坏现有 contract。
  - 缓解：先扩展 `run_contract.py`，再改 `run.py`。
- 风险：日志封装隐藏异常来源，导致调试更难。
  - 缓解：`StageLogger` 只负责输出，不捕获断言异常；失败由原脚本 / subprocess 保持原始退出码和 traceback。
- 风险：`check-project.sh` 作为主入口没有跟随新日志能力。
  - 缓解：不改 shell 参数面，使用环境变量透传，并用 `check_project_contract.py` 锁定。

## 后续可选增强

- 增加 `--log-file generated-reports/test-agent.log`，把详细日志落盘。
- 增加 JSONL 机器可读日志，供后续 CI artifact 或可视化使用。
- 将业务运行链路 `apps/analyzer/main.py` 也接入同一套日志概念，但这应另开计划，避免污染本轮测试入口改造。
