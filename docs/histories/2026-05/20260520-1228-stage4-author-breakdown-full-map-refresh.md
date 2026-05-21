# Stage 4 author breakdown full map refresh

## 背景

汇报前需要把作者画像从“低置信作者”改成可解释分类，并在不重新下载 PDF、不重跑 Stage 6 的前提下，取消作者画像数量上限，重新生成 Stage 7 地图与报告。

## 变更

- Stage 7 报告新增作者画像分类标准，区分完整画像、普通完整画像、完整画像缺指标、弱画像作者与作者跳过。
- Data Quality 不再使用“低置信作者”这种容易误解的口径，改为展示各类作者画像数量。
- 续跑脚本默认跳过 arXiv identity check，避免 Stage 4/7 展示续跑时触发不必要的 arXiv 429。
- 使用 `generated-reports/2507-19457/stage6-report-snapshot.json` 作为输入，只重跑 Stage 4 和 Stage 7。
- 本次运行不传 `--author-profile-limit`，因此不会人为跳过未缓存作者画像请求。
- 作者画像现在保留 OpenAlex work authorship 的 `countries`，Stage 7 国家/地区分布优先使用明确国家代码/国家名，再把作者名、OpenAlex ID、机构和国家提示交给 LLM 判断。
- LLM 国家判断不再因为 `needs_review=true` 或 `confidence=low` 自动改成 `Unknown`；只要模型给出国家，就保留国家并在 trace 中记录 `basis`、`is_inferred` 和中文原因。

## 验证

- `python -m py_compile scripts/test_agent/e2e_resume_stage4_stage7_from_report.py packages/reporting/service.py`
- `python scripts/test_agent/stage7.py`
- `python scripts/test_agent/e2e_resume_stage4_stage7_from_report.py --target https://arxiv.org/pdf/2507.19457 --stage6-report generated-reports/2507-19457/stage6-report-snapshot.json --max-citations 10000 --log detail`
- `python -m py_compile packages/shared/models.py packages/author_intel/service.py packages/reporting/country_resolution.py packages/reporting/service.py`
- `python scripts/test_agent/stage7.py`

## 结果

- 施引文献：157 篇。
- 作者画像：835 位作者。
- 完整作者画像：826 位。
- 重量级作者：4 位。
- 高影响力作者：56 位。
- 普通完整画像：766 位。
- 完整画像缺指标：0 位。
- 弱画像作者：9 位。
- 作者跳过：21 篇施引论文。
- 国家/地区分布已按全量作者画像重新生成。
- 新国家解析口径下，`Unknown` 从 557 降到 526。
- 明确 OpenAlex 国家提示直接归类：68 位作者。
- LLM 成功归类：241 位作者。
- 仍为 Unknown：524 位缺少国家代码/国家名/机构字段，2 位经 LLM 判断仍不足。

## 风险

- `report.pdf` 在本次覆盖时被其他进程占用，Stage 7 无法覆盖旧文件；已用同一份最新 `report.json` 额外渲染 `report-latest.pdf`。
- 国家/地区地图仍受 OpenAlex 原始国家/机构覆盖率限制；缺少国家代码、国家名和机构字段的作者仍会进入 `Unknown`。
- Stage 6 没有重跑，引用上下文与情感结果沿用既有快照。
