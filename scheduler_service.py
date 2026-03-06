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

    # 返回详细统计
    hdy_downloaded = stats["hdy"]["downloaded"]
    ehd_downloaded = stats["ehd"]["downloaded"]
    return {
        "total": hdy_downloaded + ehd_downloaded,
        "互动易": hdy_downloaded,
        "e 互动": ehd_downloaded,
    }


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
    return {"PDF 纪要": total_downloaded}


def run_news_cls():
    """执行财联社新闻爬虫"""
    from crawlers.news_cls import CLSTelegraphCrawler

    crawler = CLSTelegraphCrawler()
    count = crawler.crawl(pages=3)
    return count


def run_news_yicai():
    """执行第一财经新闻爬虫"""
    from crawlers.news_yicai import YiCaiNewsCrawler

    crawler = YiCaiNewsCrawler()
    count = crawler.crawl(pages=2)
    return count


def run_news_gov_stats():
    """执行国家统计局新闻爬虫"""
    from crawlers.news_gov_stats import GovStatsCrawler

    crawler = GovStatsCrawler()
    count = crawler.crawl(pages=3)
    return count


def run_news_pbc():
    """执行中国人民银行新闻爬虫"""
    from crawlers.news_pbc import PBOCCrawler

    crawler = PBOCCrawler()
    count = crawler.crawl()
    return count


def run_news_sohu():
    """执行搜狐财经新闻爬虫"""
    from crawlers.news_sohu import SohuFinanceCrawler

    crawler = SohuFinanceCrawler()
    count = crawler.crawl(pages=3)
    return count


def run_news_cnstock():
    """执行上海证券报爬虫"""
    from crawlers.news_cnstock import CNStockCrawler

    crawler = CNStockCrawler()
    count = crawler.crawl(pages=2)
    return count


def run_news_hkex():
    """执行港交所新闻爬虫"""
    from crawlers.news_hkex import HKEXNewsCrawler

    crawler = HKEXNewsCrawler()
    count = crawler.crawl()
    return count


def run_cls_reference():
    """执行财联社深度爬虫"""
    from crawlers.cls_reference import CLSReferenceCrawler

    crawler = CLSReferenceCrawler()
    count = crawler.crawl(pages=3)
    return count


def run_stcn_kuaixun():
    """执行证券时报快讯爬虫"""
    from crawlers.stcn_kuaixun import STCNKuaixunCrawler

    crawler = STCNKuaixunCrawler()
    count = crawler.crawl(pages=3)
    return count


def run_cninfo_announcement():
    """执行巨潮资讯公告爬虫"""
    from crawlers.cninfo_announcement import CNInfoAnnouncementCrawler

    crawler = CNInfoAnnouncementCrawler()
    count = crawler.crawl()
    return count


def run_eastmoney_news():
    """执行东方财富新闻爬虫"""
    from crawlers.eastmoney_news import EastMoneyNewsCrawler

    crawler = EastMoneyNewsCrawler()
    count = crawler.crawl(pages=3)
    return count


# 任务注册表
JOB_REGISTRY = {
    "chemical_price": run_chemical_price,
    "chemical_utilization": run_chemical_utilization,
    "ak_irm": run_ak_irm,
    "ir_pdf": run_ir_pdf,
    "news_cls": run_news_cls,
    "news_yicai": run_news_yicai,
    "news_gov_stats": run_news_gov_stats,
    "news_pbc": run_news_pbc,
    "news_sohu": run_news_sohu,
    "news_cnstock": run_news_cnstock,
    "news_hkex": run_news_hkex,
    "cls_reference": run_cls_reference,
    "stcn_kuaixun": run_stcn_kuaixun,
    "cninfo_announcement": run_cninfo_announcement,
    "eastmoney_news": run_eastmoney_news,
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
