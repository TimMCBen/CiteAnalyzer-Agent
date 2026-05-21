# Stage 4/7 final-report resume path

## 背景

汇报前需要在不重复下载 PDF、不重新跑完整全链路的情况下，复用已有 Stage 6 结果并补齐 Stage 4 作者画像与 Stage 7 展示报告。

## 变更

- 新增 `scripts/test_agent/e2e_resume_stage4_stage7_from_report.py`，从既有 Stage 6 `report.json` 恢复引用上下文，只重跑 Stage 4 和 Stage 7。
- 在恢复脚本内加入 OpenAlex work/author JSON 磁盘缓存，默认路径为 `downloaded-papers/stage4-cache/openalex-work-author-cache.json`。
- 当 Stage 6 快照缺少施引论文标题时，脚本会用 Semantic Scholar 轻量重建施引论文清单，并把旧上下文按 `citing-*` 编号对回。
- 增加空报告保护：除非显式传入 `--allow-empty`，否则输入报告无法恢复施引论文时会拒绝生成空报告。
- 支持 `--author-profile-limit` 展示模式，限制未缓存 OpenAlex author profile 请求数量；未补全作者仍保留 work-authorship 弱画像。

## 验证

- `python -m py_compile scripts/test_agent/e2e_resume_stage4_stage7_from_report.py`
- `python scripts/test_agent/stage7.py`
- 使用 `generated-reports/2507-19457/stage6-report-snapshot.json` 续跑 Stage 4/7，生成 `generated-reports/2507-19457/report.html`、`report.json`、`report.pdf`。

## 结果

- 目标论文：`2507.19457`
- 施引文献：157 篇
- 作者画像：835 位作者
- 作者画像跳过：21 篇施引论文
- 引用情感：正向 25 / 中性 21 / 批评 22 / 未知 89
- PDF 导出状态：generated

## 风险

- 展示运行使用了 `--author-profile-limit 120`，因此部分作者没有完整 h-index/citation profile，只保留 work-authorship 弱画像。
- Stage 6 快照中的上下文来自 PDF-only + GROBID 路径，GROBID 未命中或缺 PDF 的施引论文仍为 unknown。
