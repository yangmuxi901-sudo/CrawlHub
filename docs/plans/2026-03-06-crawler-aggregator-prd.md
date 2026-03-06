# 爬虫聚合器平台 PRD（两阶段版）

## 阶段一：产品需求 PRD

### 1. 产品定位
1. 产品名：`Crawler Aggregator Platform`（爬虫聚合器平台）
2. 目标：统一采集多来源数据，对外以标准“增量批次”服务多个下游系统。
3. 边界：只做采集、标准化、导出、调度、监控；不做下游分析与报告。

### 2. 背景问题
1. 爬虫来源多、格式不统一，复用成本高。
2. 原始下载文件量大，直接目录联动会重复处理且难排障。
3. 多项目共用数据时缺少统一契约与增量机制。

### 3. 目标与非目标
1. P0 目标：标准批次导出、幂等、可调度、可观测、多消费者消费。
2. 非目标：不重写全部历史爬虫；不引入重型流式中间件；不并仓 legacy。

### 4. 用户与场景
1. 平台维护者：配置抓取源、调度任务、排障。
2. 消费方开发者：按批次增量拉取标准事件。
3. 核心场景：每日采集后产出批次，下游按各自 watermark 独立消费。

### 5. 需求清单（业务）
1. 数据源分层：主链路源与 legacy 源分离。
2. 统一事件模型：固定必填字段 + 可选扩展字段。
3. 批次协议：`events.jsonl`、`manifest.json`、`_SUCCESS`。
4. 多消费者：支持不同 `consumer_id` 独立消费位点。
5. 失败隔离：单源失败不阻断全局导出。
6. 可追溯：每条事件可回溯原始链接或原始文件。

### 6. 验收口径（业务）
1. 完整性：批次统计与文件行数一致。
2. 可消费性：无 `_SUCCESS` 批次必须不可消费。
3. 质量：必填字段完整率 >= 99%。
4. 幂等：相同输入重复执行无重复新增。

---

## 阶段二：技术实施 PRD

### 7. 总体架构
1. `connectors`：各抓取源适配。
2. `normalizers`：源字段映射到统一事件。
3. `deduper`：主键去重 + 哈希兜底。
4. `exporter`：批次落盘与原子完成标记。
5. `scheduler`：任务编排、重试、补跑。
6. `monitoring`：运行日志、统计 API、告警。

### 8. 统一数据契约（v1）

#### 8.1 events.jsonl 字段
1. 必填：`event_id, source, source_id, title, published_at, url, event_type, ingested_at`
2. 可选：`symbol, company, content_text, attachments, file_path, meta`
3. 编码：UTF-8；时间：ISO8601（`+08:00`）

#### 8.2 manifest.json 字段
1. `batch_id`
2. `producer`
3. `generated_at`
4. `schema_version`
5. `record_count`
6. `sources`
7. `failed_sources`
8. `checksum`（`events.jsonl` sha256）

#### 8.3 event_id 稳定规则
1. IR：`ir:{ticker}:{publish_date}:{file_hash}`
2. IRM：`irm:{platform}:{ticker}:{publish_date}:{question_hash}`
3. NEWS：`news:{source}:{url_hash}`
4. CHEM：`chem:{metric}:{trade_date}:{entity}`

### 9. 存储与位点
1. 生产位点：`state/producer_watermark.json`（按 source）
2. 消费位点：`state/consumers/{consumer_id}.json`
3. 批次目录：`exports/YYYYMMDD_HHMMSS/`
4. 约束：`_SUCCESS` 必须最后写入。

### 10. 与现有项目映射（股东报告）
1. IR：`data/ir_pdfs` + `download_history`
2. IRM：`data/ak_irm` + `ak_irm_history`
3. 新闻：`finance_news`
4. 化工：`industry_metrics` / `output/*.csv`
5. legacy：`standalone_irm_downloader.py`、`JustSimpleSpider/` 不进默认主链路

### 11. 调度编排
1. 采集任务按源执行。
2. 标准化与去重在导出前统一执行。
3. 每日统一导出批次，或采集后触发导出。
4. 失败策略：源内重试 + 全局不中断。

### 12. API/管理面（最小集）
1. `GET /api/batches?limit=N`：批次列表
2. `GET /api/batches/{batch_id}/manifest`：批次元数据
3. `GET /api/jobs/recent`：最近任务状态
4. `GET /api/sources/stats`：分源产量与失败率

### 13. 测试与验收（技术）
1. 单元测试：字段映射、event_id 生成、去重逻辑。
2. 集成测试：从源数据到批次导出全链路。
3. 回归测试：重复执行幂等、失败重跑正确。
4. 性能基线：1 万条事件导出 < 5 分钟（单机）。

### 14. 交付清单
1. 统一 Schema 文档（v1）
2. 导出器实现与样例批次
3. watermark 机制（producer + consumer）
4. 调度编排与运行日志
5. API 最小集
6. 运维手册与故障处理手册

### 15. 里程碑
1. M1（3 天）：契约定稿 + 批次导出骨架
2. M2（5 天）：四类主源接入 + 去重 + 位点
3. M3（3 天）：调度联通 + API + 监控
4. M4（2 天）：联调验收 + 文档冻结

---

## 附录 A：manifest.json 示例
```json
{
  "batch_id": "20260306_083000",
  "producer": "crawler-aggregator",
  "generated_at": "2026-03-06T08:30:00+08:00",
  "schema_version": 1,
  "record_count": 1234,
  "sources": ["ir_pdf", "ak_irm", "finance_news", "chemical"],
  "failed_sources": [],
  "checksum": "sha256:xxxxxxxx"
}
```

## 附录 B：events.jsonl 示例
```json
{"event_id":"news:cls:ab12...","source":"news_cls","source_id":"https://www.cls.cn/detail/123","title":"...","published_at":"2026-03-06T08:21:00+08:00","url":"https://www.cls.cn/detail/123","event_type":"macro_news","ingested_at":"2026-03-06T08:30:01+08:00","content_text":"...","meta":{"author":"","tags":[]}}
```
