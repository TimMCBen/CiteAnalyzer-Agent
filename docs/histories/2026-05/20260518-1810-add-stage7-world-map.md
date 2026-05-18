# Add Stage 7 world map rendering

## 背景

Stage 7 报告已经能输出国家/地区分布，但 HTML 页面仍用横向柱状图展示，和“大作业要求的引用来源地图”不完全一致。同时目标论文标题区只展示英文标题和 DOI，arXiv 目标论文在 DOI 缺失时缺少可读链接。

## 变更

- 新增 `packages/reporting/map_data.py`，统一加载本地世界 GeoJSON，并把 `United States`、`Hong Kong` 等报告国家名映射为地图数据名称。
- 新增 `packages/reporting/static/world.geo.json` 和来源说明，使用 DataHub / Natural Earth 开放边界数据，并通过 `scripts/dev/simplify_world_geojson.py` 简化边界以降低 HTML 嵌入体积。
- 新增 `scripts/dev/report_world_map_demo.html`，先独立验证 ECharts `registerMap`、`type: "map"`、`visualMap` 和 Unknown 不上图的行为。
- Stage 7 HTML 将 `country_distribution` 渲染为国家/地区地图，并保留 fallback 列表；Unknown 和未映射地区不会被强行归并到某个国家。
- 报告标题区新增中文标题、DOI、arXiv 链接展示；中文标题通过配置的 LLM 尝试翻译，失败时只记录 warning，不阻塞报告。
- PDF 标题区同步显示中文标题和 arXiv 链接。
- 新增 `scripts/test_agent/report_map_demo_contract.py`，并将地图 demo 合同加入默认聚合验证。

## 验证

- `D:\ProgramData\Anaconda3\python.exe -m json.tool packages\reporting\static\world.geo.json > NUL`
- `D:\ProgramData\Anaconda3\python.exe scripts\test_agent\report_map_demo_contract.py`
- `D:\ProgramData\Anaconda3\python.exe scripts\test_agent\stage7.py`
- `D:\ProgramData\Anaconda3\python.exe -m compileall apps packages scripts`
- `D:\ProgramData\Anaconda3\python.exe scripts\test_agent\run.py`
- `git diff --check`

## 注意

聚合 e2e 验证期间 arXiv 出现过 `429` 和 `ReadTimeout` warning，但流程按现有降级策略继续完成并生成 HTML / JSON / PDF 报告；这属于外部网络/API 波动，不是本次地图渲染改动引入的失败。
