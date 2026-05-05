# 前端协作说明

当前仓库没有独立 SPA / Web 前端工程。
当前真实前端表面是 `packages/reporting/service.py` 生成的静态 HTML 报告页面。

## 当前前端边界

- 交付形式：HTML-first 报告页面 + JSON 数据导出
- 代码边界：前端结构和样式优先收敛在 `packages/reporting/`
- 验证入口：`python scripts/test_agent/stage7.py`
- 非目标：当前不引入 React / Vue / npm 依赖，不把报告层升级为实时服务

## 当前报告前端结构

- 顶部 hero 区：目标论文标题与 DOI
- 页面导航：overview / metrics / findings / attention / contexts
- 指标网格：关键指标卡 + trend/map/distribution 列表卡
- 注意事项区：单独 attention list
- 引用上下文区：context list + sentiment tag

## 协作要求

- 报告页面改动优先先补 `stage7.py` 断言，再改实现
- 前端升级先解决信息架构和可读性，再考虑更强交互
- 若报告结构或交付边界变化，同步更新 `docs/ARCHITECTURE.md`、产品规格和 history
