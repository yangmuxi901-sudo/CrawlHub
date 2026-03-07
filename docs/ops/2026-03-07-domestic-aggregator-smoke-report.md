# 国内聚合新闻冒烟验证记录（2026-03-07）

## 1. 验证目标
- 确认新增任务可被调度器执行。
- 确认无 API Key 场景下任务不会失败中断。
- 确认数据库查询可用。

## 2. 执行命令

```bash
python scheduler_service.py --run-now news_juhe_domestic
python scheduler_service.py --run-now news_tianapi_domestic
```

## 3. 实际结果

### 3.1 Juhe 任务
- 状态：成功执行（任务完成）
- 处理记录：0
- 原因：未配置 `JUHE_API_KEY`，按预期跳过并返回 0

### 3.2 TianAPI 任务
- 状态：成功执行（任务完成）
- 处理记录：0
- 原因：未配置 `TIANAPI_API_KEY`，按预期跳过并返回 0

### 3.3 数据库验证

验证 SQL（Python 执行）：

```sql
SELECT source, COUNT(*)
FROM finance_news
WHERE source IN ('聚合-Juhe','聚合-TianAPI')
GROUP BY source;
```

查询结果：

```text
[]
```

解释：当前无 key，聚合源尚未入库，符合预期。

## 4. 结论
- 调度接入：通过
- 任务容错（无 key）：通过
- 入库链路：待配置 key 后进行二次验证

## 5. 下一步（启用后）
1. 配置 `JUHE_API_KEY` 与 `TIANAPI_API_KEY`
2. 在 `config/scheduler.yaml` 将以下任务改为 `enabled: true`
   - `news_juhe_domestic`
   - `news_tianapi_domestic`
3. 重跑本报告命令并复核数据库中新增来源统计
