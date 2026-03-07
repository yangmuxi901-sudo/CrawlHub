# 国内聚合新闻运行手册（Juhe + TianAPI）

## 1. 目标
- 以聚合 API 替代部分逐站爬虫，降低反爬维护成本。
- 与现有 `finance_news` 表保持一致，避免下游改造。

## 2. 环境变量

### 2.1 Juhe
- `JUHE_API_KEY`：必填
- `JUHE_API_URL`：可选，默认 `http://v.juhe.cn/toutiao/index`
- `JUHE_NEWS_TYPE`：可选，默认 `caijing`

### 2.2 TianAPI
- `TIANAPI_API_KEY`：必填
- `TIANAPI_API_URL`：可选，默认 `https://apis.tianapi.com/caijing/index`
- `TIANAPI_WORD`：可选关键词

## 3. 本地执行

```bash
python crawlers/news_domestic_aggregator.py
```

## 4. 调度执行

```bash
python scheduler_service.py --run-now news_juhe_domestic
python scheduler_service.py --run-now news_tianapi_domestic
```

## 5. 调度配置建议

`config/scheduler.yaml`：
- `news_juhe_domestic`：`*/20 9-17 * * 1-5`
- `news_tianapi_domestic`：`*/30 9-17 * * 1-5`
- 默认 `enabled: false`，确认 key 后再启用

## 6. 验证 SQL

```sql
SELECT source, COUNT(*), MAX(pub_date)
FROM finance_news
WHERE source IN ('聚合-Juhe', '聚合-TianAPI')
GROUP BY source;
```

## 7. 常见问题

1. 返回 0 条：
- 检查 API Key 是否生效
- 检查当天免费额度是否耗尽

2. 调度任务失败：
- 检查 `scheduler.log` 错误信息
- 先用 `--run-now` 单任务验证
