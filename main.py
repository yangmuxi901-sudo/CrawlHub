#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
化工数据爬虫 - 统一调度入口
功能:
  1. 爬取隆众资讯化工产品价格（13大类）
  2. 爬取主要产品开工率
  3. 导出 CSV
  4. 导入 industry_metrics 表

用法:
    python main.py                  # 全量运行（价格+开工率+导入）
    python main.py --price-only     # 仅爬价格
    python main.py --util-only      # 仅爬开工率
    python main.py --no-import      # 爬取但不导入数据库
"""

import os
import sys
import argparse
from datetime import datetime

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from crawlers.base import Logger, OUTPUT_DIR, init_chemical_db
from crawlers.akshare_chem_crawler import AkShareChemFuturesCrawler
from crawlers.oilchem_utilization import OilchemUtilizationCrawler
from storage.csv_exporter import export_prices_csv, export_utilization_csv
from scripts.import_chemical_data import import_prices, import_utilization

logger = Logger(tag="MAIN")


def main():
    parser = argparse.ArgumentParser(description="化工数据爬虫调度入口")
    parser.add_argument("--price-only", action="store_true", help="仅爬取价格")
    parser.add_argument("--util-only", action="store_true", help="仅爬取开工率")
    parser.add_argument("--no-import", action="store_true", help="不导入数据库")
    args = parser.parse_args()

    run_price = not args.util_only
    run_util = not args.price_only

    init_chemical_db()

    logger.log("=" * 60)
    logger.log("化工数据爬虫系统启动")
    logger.log(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.log(f"任务: 价格={'是' if run_price else '否'} | "
               f"开工率={'是' if run_util else '否'} | "
               f"导入={'否' if args.no_import else '是'}")
    logger.log("=" * 60)

    price_csv = None
    util_csv = None

    # ===== 1. 爬取价格 =====
    if run_price:
        logger.log("--- 阶段1: 爬取化工产品价格 ---")
        crawler = AkShareChemFuturesCrawler()
        df_price = crawler.run()
        if not df_price.empty:
            paths = export_prices_csv(df_price, OUTPUT_DIR)
            if paths:
                price_csv = paths[-1]  # 最新版本路径
                logger.log(f"价格数据已导出: {paths}")
        else:
            logger.log("价格爬取无数据", "WARNING")

    # ===== 2. 爬取开工率 =====
    if run_util:
        logger.log("--- 阶段2: 爬取开工率数据 ---")
        crawler = OilchemUtilizationCrawler()
        df_util = crawler.run()
        if not df_util.empty:
            paths = export_utilization_csv(df_util, OUTPUT_DIR)
            if paths:
                util_csv = paths[-1]
                logger.log(f"开工率数据已导出: {paths}")
        else:
            logger.log("开工率爬取无数据", "WARNING")

    # ===== 3. 导入数据库 =====
    if not args.no_import:
        logger.log("--- 阶段3: 导入 industry_metrics ---")
        total = 0
        if price_csv and os.path.exists(price_csv):
            total += import_prices(price_csv)
        if util_csv and os.path.exists(util_csv):
            total += import_utilization(util_csv)
        logger.log(f"数据库导入完成: {total} 条")

    logger.log("=" * 60)
    logger.log("化工数据爬虫系统运行结束")
    logger.log("=" * 60)


if __name__ == "__main__":
    main()
