# AKShare 迁移矩阵（2026-03-08）

适用范围：`E:\Data-Fin\股东报告` 当前调度任务  
目标：明确哪些源可“AKShare 优先”，哪些必须“官方直连兜底”

## 1. 结论摘要

1. 可直接 AKShare 化（优先）：`chemical_price`、`chemical_utilization`、`ak_irm`、`news_cls`。  
2. 可部分 AKShare 化（谨慎）：`eastmoney_news`、`cninfo_announcement`（以公告列表接口为辅，不替代官方直连）。  
3. 暂不建议 AKShare 化：`ir_pdf`、`news_yicai`、`news_sohu`、`news_cnstock`、`news_hkex`、`cls_reference`、`stcn_kuaixun`、`news_juhe_domestic`、`news_tianapi_domestic`。

说明：本结论基于本地 `akshare` 实际可见函数名扫描（2026-03-08），非仅经验判断。

## 2. 本地 AKShare 关键可见函数（节选）

- 互动问答：`stock_irm_cninfo`、`stock_irm_ans_cninfo`、`stock_sns_sseinfo`
- 财联社：`stock_info_global_cls`
- 东方财富新闻：`stock_news_em`
- 巨潮公告相关：`stock_zh_a_disclosure_report_cninfo`、`stock_zh_a_disclosure_relation_cninfo`
- 宏观：`macro_*`（大量可用）
- 化工期货/现货：`futures_spot_price`、`futures_spot_price_previous`、`futures_zh_realtime`、`futures_inventory_99`

## 3. 任务级迁移矩阵

| 任务 | 当前实现 | AKShare 覆盖 | 推荐策略 | 优先级 |
|---|---|---|---|---|
| `chemical_price` | 已用 AkShare | 完整 | 维持 AKShare 主链路，保留多源重试 | P0 |
| `chemical_utilization` | AkShare 组合指标 | 间接完整 | 维持现状，继续质量校验 | P0 |
| `ak_irm` | 已用 AkShare | 完整 | 维持现状，补健康监控 | P0 |
| `news_cls` | 站点直抓 | 有 `stock_info_global_cls` | 改为 AKShare 主用，原爬虫兜底 | P1 |
| `eastmoney_news` | 站点/API抓取 | 有 `stock_news_em` | 改为 AKShare 优先，保留原实现兜底 | P1 |
| `cninfo_announcement` | 官方 API 直连 | 有部分披露接口 | 官方直连为主，AKShare 做降级替代 | P1 |
| `ir_pdf` | 巨潮 PDF 直下 | 无等价直下能力 | 保持官方直连，不迁移 | P0 |
| `news_yicai` | 站点/API抓取 | 未发现直连函数 | 保留现状 | P2 |
| `news_sohu` | 站点抓取 | 未发现直连函数 | 保留现状 | P2 |
| `news_cnstock` | 站点抓取 | 未发现直连函数 | 保留现状（优先修反爬） | P2 |
| `news_hkex` | Playwright 抓取 | 未发现直连函数 | 保留现状 | P2 |
| `cls_reference` | 站点/API抓取 | 无等价深度栏目 | 保留现状 | P2 |
| `stcn_kuaixun` | 站点/API抓取 | 未发现直连函数 | 保留现状 | P2 |
| `news_juhe_domestic` | 第三方聚合 | 非 AKShare 范畴 | 保留为 L3 补充源 | P3 |
| `news_tianapi_domestic` | 第三方聚合 | 非 AKShare 范畴 | 保留为 L3 补充源 | P3 |

## 4. 半导体场景（M0.1）建议落地

### 4.1 宏观层（常开）
- 优先 AKShare `macro_*` 系列（利率、PMI、流动性指标等）
- 用于“风险状态”输入，不直接当新闻结论

### 4.2 主题层（半导体）
- `news_cls` 优先 AKShare 化（P1）
- `eastmoney_news` 优先 AKShare 化（P1）
- `cninfo_announcement` 维持官方直连主链路（P1），AKShare 仅作退化兜底

### 4.3 持仓层（动态）
- 与 AKShare 无强耦合，按 `portfolio_today.json` 做映射聚合即可

## 5. 执行顺序（建议）

1. `news_cls` AKShare 主链路改造（保留旧链路 fallback）  
2. `eastmoney_news` AKShare 主链路改造（保留旧链路 fallback）  
3. `cninfo_announcement` 增加 AKShare 退化路径（不替换官方主链路）  
4. 宏观层接入最小 `macro_*` 指标集（服务 M0.1）

## 6. 风险提示

1. AKShare 不是官方 SLA 数据源，不能替代 L1 官方源。  
2. 同步迁移时必须保留现有“源头筛选 + 健康看板 + degrade”机制。  
3. 半导体核心结论仍须遵守 `2-source` 规则。
