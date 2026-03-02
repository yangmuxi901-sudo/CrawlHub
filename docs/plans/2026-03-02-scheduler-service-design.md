# 调度服务设计文档

**日期：** 2026-03-02
**状态：** 已确认

---

## 1. 目标

为项目新增一个常驻后台调度服务，统一管理全部 4 个爬虫任务的定时执行，部署到 Mac 服务器后一键启动、自动运行。

## 2. 方案选型

**APScheduler 内置调度器 + macOS launchd 进程守护**

- APScheduler：Python 层面的定时调度，支持 cron 表达式、错过补跑
- launchd：macOS 原生进程管理，保证进程挂了自动重启

## 3. 整体架构

```
┌─────────────────────────────────────────────────────┐
│              scheduler_service.py (常驻进程)          │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │         APScheduler (BackgroundScheduler)     │    │
│  │                                               │    │
│  │  Job 1: 化工价格    cron 09:30, 18:00 (工作日) │    │
│  │  Job 2: 化工开工率  cron 18:30 (工作日)        │    │
│  │  Job 3: AKShare互动 cron 02:00 (每天)         │    │
│  │  Job 4: 巨潮PDF     cron 03:00 (每天)         │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐   │
│  │ 日志模块    │  │ 信号处理    │  │ 任务状态记录  │   │
│  │ (rotating) │  │ (graceful) │  │ (SQLite)     │   │
│  └────────────┘  └────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────┘
         │
         ▼ 函数调用（import 后直接调用）
┌─────────────────────────────────────────────────────┐
│  main.py (化工)  │  standalone_ak_irm_downloader.py  │
│                  │  standalone_ir_downloader.py       │
└─────────────────────────────────────────────────────┘
         │
         ▼ 数据存储
┌─────────────────────────────────────────────────────┐
│  data/sync_record.db  │  output/*.csv  │  data/ir_pdfs/ │
└─────────────────────────────────────────────────────┘
```

## 4. 调度配置

配置文件：`config/scheduler.yaml`

```yaml
scheduler:
  timezone: "Asia/Shanghai"

  jobs:
    chemical_price:
      enabled: true
      cron: "30 9,18 * * 1-5"       # 工作日 9:30 和 18:00
      misfire_grace_time: 3600       # 错过后 1 小时内补跑

    chemical_utilization:
      enabled: false                 # 开工率暂不可用，关闭
      cron: "30 18 * * 1-5"
      misfire_grace_time: 3600

    ak_irm:
      enabled: true
      cron: "0 2 * * *"             # 每天凌晨 2 点
      misfire_grace_time: 3600

    ir_pdf:
      enabled: true
      cron: "0 3 * * *"             # 每天凌晨 3 点
      misfire_grace_time: 3600

  logging:
    max_bytes: 10485760              # 10MB 轮转
    backup_count: 5
```

### 频率设计理由

| 任务 | 频率 | 理由 |
|------|------|------|
| 化工价格 | 工作日 9:30/18:00 | 期货市场工作日才有数据，早盘前+收盘后各取一次 |
| 化工开工率 | 工作日 18:30 | 与价格错开，避免并发竞争 |
| AKShare 互动 | 每天 02:00 | 公告随时可能发布，凌晨反爬压力最小 |
| 巨潮 PDF | 每天 03:00 | 同上，与互动任务错开 |

## 5. 任务调用方式

调度器通过函数调用（而非 subprocess）执行各爬虫：

```python
JOB_REGISTRY = {
    "chemical_price":       run_chemical_price,       # 调用 main.py 的价格逻辑
    "chemical_utilization":  run_chemical_utilization,  # 调用 main.py 的开工率逻辑
    "ak_irm":               run_ak_irm,               # 调用 standalone_ak_irm_downloader.main()
    "ir_pdf":               run_ir_pdf,                # 调用 standalone_ir_downloader.main()
}
```

每个 `run_xxx` 函数是一个轻量包装，负责：
1. 记录开始时间
2. 调用实际爬虫逻辑
3. 捕获异常
4. 记录结果到 `scheduler_run_log` 表

## 6. 执行记录

在 `data/sync_record.db` 中新增表：

```sql
CREATE TABLE scheduler_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL,           -- success / failed
    error_msg TEXT,
    records_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 7. 错误处理

| 场景 | 处理方式 |
|------|----------|
| 单个任务抛异常 | 捕获异常，写入 run_log（status=failed），不影响其他任务 |
| 任务错过（机器休眠/重启） | misfire_grace_time=3600，1 小时内补跑 |
| 调度器进程挂掉 | launchd KeepAlive 自动重启 |
| 网络超时 | 爬虫内部已有重试机制（3 次），无需额外处理 |

## 8. 现有代码修复

### 8.1 硬编码日期

`crawlers/akshare_chem_crawler.py:56` 中 `self.trade_date = "20250227"` 改为动态获取：

```python
from datetime import datetime
self.trade_date = datetime.now().strftime("%Y%m%d")
```

### 8.2 standalone_ir_downloader.py 模块化

当前 `main()` 函数直接在模块顶层运行，需要确保被 import 时不会自动执行（已有 `if __name__ == "__main__"` 保护，OK）。

## 9. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scheduler_service.py` | 新增 | 调度服务主入口 |
| `config/scheduler.yaml` | 新增 | 调度配置 |
| `deploy/com.crawlhub.scheduler.plist` | 新增 | macOS launchd 配置 |
| `requirements.txt` | 修改 | 加入 `apscheduler>=3.10.0` |
| `crawlers/akshare_chem_crawler.py` | 修改 | 修复硬编码日期 |

## 10. 日志方案

使用 Python `logging` 模块 + `RotatingFileHandler`：

- 日志文件：`data/scheduler.log`
- 轮转：10MB / 5 个备份
- 格式：`[2026-03-02 09:30:00] [INFO] [chemical_price] 任务开始`
- 同时输出到 stdout（便于 launchd 捕获）

## 11. 部署步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 前台测试
python scheduler_service.py

# 3. 部署 launchd（Mac 服务器）
cp deploy/com.crawlhub.scheduler.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.crawlhub.scheduler.plist

# 4. 查看状态
launchctl list | grep crawlhub

# 5. 停止服务
launchctl unload ~/Library/LaunchAgents/com.crawlhub.scheduler.plist
```

## 12. 启动方式

```bash
# 默认启动（使用 config/scheduler.yaml）
python scheduler_service.py

# 指定配置文件
python scheduler_service.py --config /path/to/scheduler.yaml

# 立即执行某个任务（调试用）
python scheduler_service.py --run-now chemical_price
```
