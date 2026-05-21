# Stage 1 web-search title fallback

## 背景

目标论文解析依赖 arXiv API 时，遇到 ReadTimeout 或 429 会降级成 `arXiv:<id>`，导致报告标题和中文标题展示异常。需要在 Stage 1 中加入可配置的联网搜索兜底，让模型基于搜索结果判断真实论文标题。

## 变更

- 新增 `packages/shared/web_search.py`，提供可配置的通用搜索 API 客户端。
- 支持 `WEB_SEARCH_PROVIDER=tavily|brave|serpapi`。
- 对应 key 为 `TAVILY_API_KEY`、`BRAVE_SEARCH_API_KEY`、`SERPAPI_API_KEY`，也支持通用 `WEB_SEARCH_API_KEY`。
- Stage 1 arXiv 解析失败时，先尝试 Semantic Scholar 按 `ARXIV:<id>` 补标题。
- Semantic Scholar 也失败时，调用通用搜索 API 检索 `arXiv <id> paper title`，再让 LLM 从搜索结果中结构化核验标题。
- 如果搜索结果无法可靠对应指定 arXiv ID，LLM 必须返回 `UNKNOWN`，代码不会采用该标题。

## 验证

- `python -m py_compile apps\analyzer\resolve.py packages\shared\web_search.py scripts\test_agent\stage1.py`
- `python scripts\test_agent\stage1.py`
- 真实调用 `resolve_target_paper_metadata(TargetPaper(...2507.19457...))`，返回标题 `GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning`。

## 风险

- 当前 `.env` 没有配置搜索 API key，因此真实联网搜索兜底默认不会启用；未配置时会明确记录 warning 并继续降级。
- 通用搜索 API 返回的是网页摘要，不是权威数据库；因此仍必须经过 LLM 核验，且只在 arXiv/Semantic Scholar 等结构化来源失败后使用。
