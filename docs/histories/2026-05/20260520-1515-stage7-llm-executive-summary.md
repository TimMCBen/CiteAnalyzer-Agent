# Stage 7 LLM 分析摘要文案

## 用户诉求

用户希望继续优化 Stage 7 报告展示，把分析摘要这类读者文案尽量改为通过已有 LLM API 和提示词生成，并避免读者看到内部字段名或误导性表述。

## 主要改动

- 在 `packages/reporting/service.py` 中新增结构化 `ExecutiveSummaryModel` 和 Stage 7 分析摘要生成链路。
- Stage 7 先整理可控事实字段，再调用 `.env` 配置的 LLM 生成 4 到 5 条中文摘要。
- 提示词明确约束不要输出 `citation_count`、`dedup_author_count`、`unknown_sentiments` 等内部字段名。
- 提示词要求解释未知情感来源、重要学者候选规则和去重施引作者口径。
- 新增摘要清洗规则；如果 LLM 输出仍包含内部字段或误导词，会回退到确定性中文摘要。
- `scripts/test_agent/stage7.py` 注入固定摘要生成器，保证合同测试不依赖真实 LLM，同时覆盖关键中文文案。
- 将 HTML 中的“数据覆盖情况”从分析摘要卡片内移到调试附录上方，作为独立主报告区块，减少摘要区信息拥挤。
- 移除顶部四个核心指标卡片，将“分析摘要”移动到原指标卡片位置；四个小图表移动到右栏，国家/地区地图保留在左侧主内容区。
- 右栏四个小图表改为紧凑 2x2 网格，并放宽右栏宽度以减少图表拥挤。
- 四个图表上移到页面顶部右侧，与左侧标题/摘要区域并列；下方右栏只保留“重要学者”。
- 压缩右栏图卡标题、说明文字和图表高度，使四个图在演示页中更紧凑。
- 为 Stage 4/7 resume 脚本增加可信标题覆盖参数，避免展示报告重生成时被临时 arXiv / Semantic Scholar 网络失败污染标题。

## 验证

- `python -m py_compile packages\reporting\service.py scripts\test_agent\stage7.py`
- `python scripts\test_agent\stage7.py`
- 使用既有 `2507-19457` 报告快照重新运行 Stage 4 + Stage 7，确认摘要来源为 `llm`，HTML/PDF/JSON 已重新生成。
- 使用浏览器 DOM 测量确认四个小图表位于顶部右侧 2x2，单图面板高度为 140px，且与标题区域顶部对齐。

## 影响文件

- `packages/reporting/service.py`
- `scripts/test_agent/stage7.py`
- `generated-reports/2507-19457/report.html`
- `generated-reports/2507-19457/report.json`
- `generated-reports/2507-19457/report.pdf`
