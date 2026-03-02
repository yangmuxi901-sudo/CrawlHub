# 调度服务实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为项目新增 APScheduler 常驻调度服务，统一管理 4 个爬虫的定时执行，部署到 Mac 服务器。

**Architecture:** 新增 `scheduler_service.py` 作为常驻进程，通过 APScheduler BackgroundScheduler 按 cron 表达式调度各爬虫。调度配置存储在 `config/scheduler.yaml`，执行记录写入 SQLite `scheduler_run_log` 表。macOS launchd plist 保证进程自动重启。

**Tech Stack:** Python 3.8+, APScheduler 3.10+, SQLite3, macOS launchd

**Design Doc:** `docs/plans/2026-03-02-scheduler-service-design.md`

---

### Task 1: 修复硬编码日期

**Files:**
- Modify: `crawlers/akshare_chem_crawler.py:55-56`

**Step 1: 修改硬编码日期为动态获取**

将第 55-56 行：

```python
        # 固定使用 20250227 数据（最近交易日）
        self.trade_date = "20250227"
```

改为：

```python
        # 动态获取当天日期
        self.trade_date = datetime.now().strftime("%Y%m%d")
```

文件顶部已有 `from datetime import datetime`（第 11 行），无需额外 import。

**Step 2: 验证修改**

运行：`python -c "from crawlers.akshare_chem_crawler import AkShareChemFuturesCrawler; c = AkShareChemFuturesCrawler(); print(c.trade_date)"`

预期输出：当天日期，如 `20260302`

**Step 3: 提交**

```bash
git add crawlers/akshare_chem_crawler.py
git commit -m "fix: 化工价格爬虫日期改为动态获取，移除硬编码 20250227"
```

---

### Task 2: 添加 APScheduler 依赖

**Files:**
- Modify: `requirements.txt`

**Step 1: 在 requirements.txt 末尾添加 apscheduler**

在文件末尾（`# 可选依赖` 注释之前）添加：

```
apscheduler>=3.10.0
```

最终文件内容：

```
requests>=2.28.0
pandas>=1.5.0
pyyaml>=6.0
beautifulsoup4>=4.12.0
apscheduler>=3.10.0
# 可选依赖（备选数据源）
# akshare>=1.10.0
# playwright>=1.40.0
```

**Step 2: 安装依赖**

运行：`pip install apscheduler>=3.10.0`

预期：安装成功

**Step 3: 验证 import**

运行：`python -c "from apscheduler.schedulers.background import BackgroundScheduler; print('OK')"`

预期输出：`OK`

**Step 4: 提交**

```bash
git add requirements.txt
git commit -m "deps: 添加 apscheduler 依赖"
```

---

### Task 3: 创建调度配置文件

**Files:**
- Create: `config/scheduler.yaml`

**Step 1: 创建 config/scheduler.yaml**

```yaml
# 调度服务配置
# cron 格式：分 时 日 月 星期（0=周日，1-5=周一至周五）

scheduler:
  timezone: "Asia/Shanghai"

  jobs:
    chemical_price:
      enabled: true
      cron: "30 9,18 * * 1-5"
      misfire_grace_time: 3600

    chemical_utilization:
      enabled: false
      cron: "30 18 * * 1-5"
      misfire_grace_time: 3600

    ak_irm:
      enabled: true
      cron: "0 2 * * *"
      misfire_grace_time: 3600

    ir_pdf:
      enabled: true
      cron: "0 3 * * *"
      misfire_grace_time: 3600

  logging:
    max_bytes: 10485760
    backup_count: 5
```

**Step 2: 验证 YAML 可解析**

运行：`python -c "import yaml; cfg = yaml.safe_load(open('config/scheduler.yaml')); print(list(cfg['scheduler']['jobs'].keys()))"`

预期输出：`['chemical_price', 'chemical_utilization', 'ak_irm', 'ir_pdf']`

**Step 3: 提交**

```bash
git add config/scheduler.yaml
git commit -m "config: 添加调度服务配置文件"
```

---

### Task 4: 实现调度服务主体

**Files:**
- Create: `scheduler_service.py`

**Step 1: 创建 scheduler_service.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrawlHub 调度服务 - 常驻后台进程
统一调度全部爬虫任务，支持 cron 表达式、错过补跑、执行记录。

用法:
    python scheduler_service.py                        # 默认启动
    python scheduler_service.py --config path.yaml     # 指定配置
    python scheduler_service.py --run-now chemical_price  # 立即执行某任务
"""

import os
import sys
import signal
import time
import sqlite3
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ============== 路径常量 ==============
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config", "scheduler.yaml")
DEFAULT_LOG_PATH = os.path.join(DATA_DIR, "scheduler.log")

os.makedirs(DATA_DIR, exist_ok=True)


# ============== 日志配置 ==============
def setup_logging(log_path=DEFAULT_LOG_PATH, max_bytes=10485760, backup_count=5):
    """配置 rotating 日志"""
    logger = logging.getLogger("scheduler")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler（轮转）
    fh = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    return logger


# ============== 执行记录（SQLite） ==============
def init_run_log_table():
    """初始化 scheduler_run_log 表"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            error_msg TEXT,
            records_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def log_run(job_name, start_time, end_time, status, error_msg="", records_count=0):
    """写入一条执行记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO scheduler_run_log
           (job_name, start_time, end_time, status, error_msg, records_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (job_name, start_time, end_time, status, error_msg, records_count),
    )
    conn.commit()
    conn.close()


# ============== 爬虫任务包装 ==============
def run_chemical_price():
    """执行化工价格爬虫"""
    from crawlers.base import init_chemical_db, OUTPUT_DIR
    from crawlers.akshare_chem_crawler import AkShareChemFuturesCrawler
    from storage.csv_exporter import export_prices_csv
    from scripts.import_chemical_data import import_prices

    init_chemical_db()
    crawler = AkShareChemFuturesCrawler()
    df = crawler.run()
    count = 0
    if not df.empty:
        paths = export_prices_csv(df, OUTPUT_DIR)
        if paths:
            count += import_prices(paths[-1])
    return count


def run_chemical_utilization():
    """执行化工开工率爬虫"""
    from crawlers.base import init_chemical_db, OUTPUT_DIR
    from crawlers.oilchem_utilization import OilchemUtilizationCrawler
    from storage.csv_exporter import export_utilization_csv
    from scripts.import_chemical_data import import_utilization

    init_chemical_db()
    crawler = OilchemUtilizationCrawler()
    df = crawler.run()
    count = 0
    if not df.empty:
        paths = export_utilization_csv(df, OUTPUT_DIR)
        if paths:
            count += import_utilization(paths[-1])
    return count


def run_ak_irm():
    """执行 AKShare 互动平台下载器"""
    import standalone_ak_irm_downloader as mod

    mod.logger = mod.Logger(mod.LOG_PATH)
    mod.init_database()
    os.makedirs(mod.ATTACHMENT_DIR, exist_ok=True)

    ehd_available, _ = mod.check_ehd_api_available()
    df = mod.load_company_list()
    stats = mod.process_all_stocks(df, mod.ATTACHMENT_DIR, skip_ehd=not ehd_available)
    return stats["hdy"]["downloaded"] + stats["ehd"]["downloaded"]


def run_ir_pdf():
    """执行巨潮 PDF 下载器"""
    import standalone_ir_downloader as mod

    mod.logger = mod.Logger(mod.LOG_PATH)
    if not mod.load_orgid_mapping():
        raise RuntimeError("orgId 映射表加载失败")
    mod.init_database()
    os.makedirs(mod.PDF_DIR, exist_ok=True)

    df = mod.load_company_list()
    total_downloaded, _, _, _ = mod.process_all_stocks(df, mod.PDF_DIR)
    return total_downloaded


# 任务注册表
JOB_REGISTRY = {
    "chemical_price": run_chemical_price,
    "chemical_utilization": run_chemical_utilization,
    "ak_irm": run_ak_irm,
    "ir_pdf": run_ir_pdf,
}


# ============== 任务执行器 ==============
def execute_job(job_name, logger):
    """执行单个任务并记录结果"""
    logger.info(f"[{job_name}] 任务开始")
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        func = JOB_REGISTRY[job_name]
        count = func()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_run(job_name, start_time, end_time, "success", records_count=count or 0)
        logger.info(f"[{job_name}] 任务完成，处理 {count or 0} 条记录")
    except Exception as e:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_msg = str(e)
        log_run(job_name, start_time, end_time, "failed", error_msg=error_msg)
        logger.error(f"[{job_name}] 任务失败: {error_msg}")


# ============== 配置加载 ==============
def load_config(config_path):
    """加载调度配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["scheduler"]


# ============== 主入口 ==============
def main():
    parser = argparse.ArgumentParser(description="CrawlHub 调度服务")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="配置文件路径")
    parser.add_argument("--run-now", metavar="JOB", help="立即执行指定任务后退出")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 初始化日志
    log_cfg = config.get("logging", {})
    logger = setup_logging(
        max_bytes=log_cfg.get("max_bytes", 10485760),
        backup_count=log_cfg.get("backup_count", 5),
    )

    # 初始化执行记录表
    init_run_log_table()

    # --run-now 模式：立即执行后退出
    if args.run_now:
        job_name = args.run_now
        if job_name not in JOB_REGISTRY:
            logger.error(f"未知任务: {job_name}，可选: {list(JOB_REGISTRY.keys())}")
            sys.exit(1)
        execute_job(job_name, logger)
        sys.exit(0)

    # 创建调度器
    timezone = config.get("timezone", "Asia/Shanghai")
    scheduler = BackgroundScheduler(timezone=timezone)

    # 注册任务
    jobs_config = config.get("jobs", {})
    registered = 0
    for job_name, job_cfg in jobs_config.items():
        if not job_cfg.get("enabled", False):
            logger.info(f"[{job_name}] 已禁用，跳过")
            continue
        if job_name not in JOB_REGISTRY:
            logger.warning(f"[{job_name}] 未知任务，跳过")
            continue

        cron_expr = job_cfg["cron"]
        misfire = job_cfg.get("misfire_grace_time", 3600)

        scheduler.add_job(
            func=execute_job,
            args=(job_name, logger),
            trigger=CronTrigger.from_crontab(cron_expr, timezone=timezone),
            misfire_grace_time=misfire,
            id=job_name,
            name=job_name,
            replace_existing=True,
        )
        logger.info(f"[{job_name}] 已注册，cron: {cron_expr}")
        registered += 1

    if registered == 0:
        logger.error("没有任何任务被注册，退出")
        sys.exit(1)

    # 启动调度器
    scheduler.start()
    logger.info(f"调度服务已启动，共 {registered} 个任务，时区: {timezone}")
    logger.info("按 Ctrl+C 停止服务")

    # 优雅退出
    def shutdown(signum, frame):
        logger.info("收到退出信号，正在关闭调度器...")
        scheduler.shutdown(wait=True)
        logger.info("调度器已关闭")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # 阻塞主线程
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
```

**Step 2: 验证语法**

运行：`python -c "import py_compile; py_compile.compile('scheduler_service.py', doraise=True); print('OK')"`

预期输出：`OK`

**Step 3: 验证 --run-now 模式（化工价格）**

运行：`python scheduler_service.py --run-now chemical_price`

预期：执行化工价格爬虫，日志输出到 stdout 和 `data/scheduler.log`，执行记录写入 SQLite。

**Step 4: 验证调度器启动**

运行：`timeout 10 python scheduler_service.py || true`

预期：看到 "调度服务已启动，共 3 个任务" 日志（chemical_utilization 已禁用），10 秒后超时退出。

**Step 5: 验证执行记录写入**

运行：`python -c "import sqlite3; conn = sqlite3.connect('data/sync_record.db'); rows = conn.execute('SELECT job_name, status FROM scheduler_run_log').fetchall(); print(rows)"`

预期：至少看到 Step 3 产生的一条 `('chemical_price', 'success')` 或 `('chemical_price', 'failed')` 记录。

**Step 6: 提交**

```bash
git add scheduler_service.py
git commit -m "feat: 添加 APScheduler 调度服务主体"
```

---

### Task 5: 创建 launchd 部署配置

**Files:**
- Create: `deploy/com.crawlhub.scheduler.plist`

**Step 1: 创建 deploy 目录和 plist 文件**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crawlhub.scheduler</string>

    <key>ProgramArguments</key>
    <array>
        <!-- 部署时修改为实际的 python 和脚本路径 -->
        <string>/usr/bin/python3</string>
        <string>/path/to/scheduler_service.py</string>
    </array>

    <key>WorkingDirectory</key>
    <!-- 部署时修改为项目根目录 -->
    <string>/path/to/project</string>

    <key>KeepAlive</key>
    <true/>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/path/to/data/scheduler_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/path/to/data/scheduler_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
        <key>PYTHONIOENCODING</key>
        <string>utf-8</string>
    </dict>
</dict>
</plist>
```

**Step 2: 验证 plist 语法**

运行：`plutil -lint deploy/com.crawlhub.scheduler.plist`

预期输出：`deploy/com.crawlhub.scheduler.plist: OK`

**Step 3: 提交**

```bash
git add deploy/com.crawlhub.scheduler.plist
git commit -m "deploy: 添加 macOS launchd 配置文件"
```

---

### Task 6: 端到端集成验证

**Step 1: 验证 --run-now 全部任务**

逐个运行（跳过 chemical_utilization，已禁用）：

```bash
python scheduler_service.py --run-now chemical_price
python scheduler_service.py --run-now ak_irm
python scheduler_service.py --run-now ir_pdf
```

观察每个任务的日志输出，确认无报错。

**Step 2: 验证调度器常驻运行**

```bash
python scheduler_service.py &
sleep 5
# 确认进程存在
ps aux | grep scheduler_service | grep -v grep
# 停止
kill %1
```

预期：进程正常存在，kill 后看到 "调度器已关闭" 日志。

**Step 3: 检查执行记录完整性**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/sync_record.db')
for row in conn.execute('SELECT job_name, start_time, status, records_count FROM scheduler_run_log ORDER BY id'):
    print(row)
"
```

预期：看到 3 条记录，对应 Step 1 的 3 次执行。

**Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: 调度服务完成，全部任务验证通过"
```
