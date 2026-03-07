# 新闻采集三层架构说明

## 1. 分层目标
- 让新增新闻源只关心“如何抓”，而不是重复写入库和字段清洗逻辑。
- 将“抓取、标准化、存储”职责拆开，降低维护成本。

## 2. 三层定义

### L1 Source Adapter（源适配层）
- 位置：`crawlers/news_*.py`
- 职责：
  - 请求外部站点/API
  - 解析原始字段（title/link/time/article）
  - 返回原始列表（dict）

### L2 Normalize & Quality（标准化与质量层）
- 位置：`crawlers/news_arch/normalizer.py`
- 职责：
  - 统一字段规范（title/source/pub_date/link/article/category）
  - 时间格式标准化
  - 必填校验（空标题/空链接剔除）

### L3 Storage & Orchestration（存储与编排层）
- 位置：
  - `crawlers/news_arch/storage.py`
  - `crawlers/news_arch/pipeline.py`
  - `scheduler_service.py`
- 职责：
  - 统一建表与索引
  - 统一入库去重（`UNIQUE(link)`）
  - 统一调度任务注册与执行

## 3. 当前落地状态
- `news_domestic_aggregator.py` 已迁移到三层架构：
  - 抓取：本文件 `_fetch_juhe/_fetch_tianapi`
  - 标准化：`normalize_news_item`
  - 入库编排：`NewsIngestionPipeline + FinanceNewsStore`

## 4. 新增新闻源模板
1. 新建 `crawlers/news_xxx.py`
2. 写 `_fetch_xxx()` 仅负责抓取解析
3. 用 `pipeline.ingest(..., normalize_news_item)` 入库
4. 在 `scheduler_service.py` 新增 `run_news_xxx`
5. 在 `config/scheduler.yaml` 增加任务配置（默认 disabled）
6. 在 `web/api.py` 的 `get_jobs()` 加展示项

## 5. 为什么这样扩展更快
- 每加一个源，不再重复写 SQL/索引/去重
- 数据一致性由中层统一控制
- 调度接入成本固定，便于批量扩展
