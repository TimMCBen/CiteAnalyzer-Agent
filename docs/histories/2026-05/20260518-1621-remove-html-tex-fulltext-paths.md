## [2026-05-18 16:21] | Task: 移除 HTML / TeX 全文提取路径

### Execution Context

- **Mode**: Solo execute
- **Branch**: `feat/stage7-deliverable-report`
- **Scope**: 阶段 5 全文获取、阶段 6 引用上下文定位、相关验证脚本与架构说明

### User Request

> 把这个步骤直接Tex/HTML提取的步骤直接删了！相关的代码请彻查，然后提交一版

### Changes

- **阶段 5 收口为 PDF 主路径**: arXiv 标题搜索与 arXiv 链接候选只产出 PDF URL，不再把 arXiv HTML / abs 页作为全文候选。
- **删除 HTML / TeX 解析执行路径**: 移除 BeautifulSoup HTML 正文抽取、LaTeX 正文近似清洗、本地与远程 HTML / TeX 文档解析分支。
- **阶段 6 删除 TeX 专用节点**: 移除 TeX bibliography / citation key 匹配节点，保留 `PDF -> GROBID -> LLM/rule fallback` 路径。
- **契约收紧**: `FullTextDocument`、`TextSourceSelection`、`CitationContext` 的文本来源类型不再包含 `html` / `latex`。
- **依赖清理**: CI 依赖中移除不再使用的 `beautifulsoup4`。
- **PDF 路径稳定性**: 对 PDF 抽取文本写盘前做 UTF-8 surrogate 清洗，避免合法 PDF 抽取结果因为非法 Unicode 字符写盘失败。
- **测试同步**: Stage 5 / Stage 6 / Stage 5-6 集成测试改为 PDF fixture，并断言 arXiv fallback 只返回 PDF 候选。

### Rationale

HTML 落地页和 TeX 源码路径在真实运行中引入了额外不稳定性，也容易让阶段 6 分叉到较难解释的专用路径。当前用户明确要求删除该步骤，因此主流程改为更清晰的 PDF-first：能拿 PDF 就走 GROBID 和文本 fallback，拿不到 PDF 则降级为摘要或 unknown，不再尝试直接解析 HTML / TeX。

### Verification

- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/stage5.py`
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/stage6.py`
- `D:\ProgramData\Anaconda3\python.exe scripts/test_agent/stage56_integration.py`
