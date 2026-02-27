#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
化工数据导入脚本
将爬虫输出的 CSV 导入到 industry_metrics 表
供 AI Hedge Fund 使用

用法:
    python scripts/import_chemical_data.py
    python scripts/import_chemical_data.py --prices output/chemical_prices.csv
    python scripts/import_chemical_data.py --utilization output/chemical_utilization.csv
"""

import os
import sys
import argparse
import sqlite3
import pandas as pd
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import DB_PATH, OUTPUT_DIR, init_chemical_db, Logger, load_products_config

logger = Logger(tag="IMPORT")


def import_prices(csv_path):
    """导入价格 CSV 到 industry_metrics 表"""
    if not os.path.exists(csv_path):
        logger.log(f"文件不存在: {csv_path}", "ERROR")
        return 0

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        logger.log("CSV 为空，跳过导入", "WARNING")
        return 0

    logger.log(f"读取 {len(df)} 条价格记录")

    # 加载产品配置，获取 ticker 映射
    config = load_products_config()
    product_tickers = {}
    for p in config.get("products", []):
        product_tickers[p["name"]] = p.get("tickers", [])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0

    for _, row in df.iterrows():
        product_name = row.get("product_name", "")
        trade_date = row.get("trade_date", "")
        price = row.get("price")
        price_change = row.get("price_change", 0.0)

        # 从 CSV 的 tickers 列或配置中获取关联股票
        tickers_str = str(row.get("tickers", ""))
        if tickers_str and tickers_str != "nan":
            tickers = [t.strip() for t in tickers_str.split(",") if t.strip()]
        else:
            tickers = product_tickers.get(product_name, [])

        if not tickers:
            continue

        # 为每个关联股票插入一条记录
        for ticker in tickers:
            try:
                cursor.execute("""
                    INSERT INTO industry_metrics
                        (ticker, trade_date, industry, product_price, price_change)
                    VALUES (?, ?, '化工', ?, ?)
                    ON CONFLICT(ticker, trade_date, industry) DO UPDATE SET
                        product_price=excluded.product_price,
                        price_change=excluded.price_change
                """, (ticker, trade_date, price, price_change))
                inserted += 1
            except Exception as e:
                logger.log(f"插入失败: {ticker} {trade_date} - {e}", "WARNING")

    conn.commit()
    conn.close()
    logger.log(f"价格数据导入完成: {inserted} 条记录")
    return inserted


def import_utilization(csv_path):
    """导入开工率 CSV 到 industry_metrics 表"""
    if not os.path.exists(csv_path):
        logger.log(f"文件不存在: {csv_path}", "ERROR")
        return 0

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        logger.log("CSV 为空，跳过导入", "WARNING")
        return 0

    logger.log(f"读取 {len(df)} 条开工率记录")

    config = load_products_config()
    # 建立产品名 -> tickers 映射
    product_tickers = {}
    for p in config.get("products", []):
        product_tickers[p["name"]] = p.get("tickers", [])
        # 开工率产品名可能是简称，也做模糊匹配
        for kw in p.get("keywords", []):
            product_tickers[kw] = p.get("tickers", [])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0

    for _, row in df.iterrows():
        product_name = row.get("product_name", "")
        stat_date = row.get("stat_date", "")
        utilization_rate = row.get("utilization_rate")

        # 查找关联股票
        tickers = product_tickers.get(product_name, [])
        if not tickers:
            # 模糊匹配
            for key, vals in product_tickers.items():
                if key in product_name or product_name in key:
                    tickers = vals
                    break

        if not tickers:
            continue

        for ticker in tickers:
            try:
                cursor.execute("""
                    INSERT INTO industry_metrics
                        (ticker, trade_date, industry, capacity_utilization)
                    VALUES (?, ?, '化工', ?)
                    ON CONFLICT(ticker, trade_date, industry) DO UPDATE SET
                        capacity_utilization=excluded.capacity_utilization
                """, (ticker, stat_date, utilization_rate))
                inserted += 1
            except Exception as e:
                logger.log(f"插入失败: {ticker} {stat_date} - {e}", "WARNING")

    conn.commit()
    conn.close()
    logger.log(f"开工率数据导入完成: {inserted} 条记录")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="化工数据导入到 industry_metrics")
    parser.add_argument("--prices", default=os.path.join(OUTPUT_DIR, "chemical_prices.csv"),
                        help="价格 CSV 路径")
    parser.add_argument("--utilization", default=os.path.join(OUTPUT_DIR, "chemical_utilization.csv"),
                        help="开工率 CSV 路径")
    parser.add_argument("--skip-prices", action="store_true", help="跳过价格导入")
    parser.add_argument("--skip-utilization", action="store_true", help="跳过开工率导入")
    args = parser.parse_args()

    init_chemical_db()

    logger.log("=" * 60)
    logger.log("化工数据导入开始")
    logger.log("=" * 60)

    total = 0
    if not args.skip_prices:
        total += import_prices(args.prices)
    if not args.skip_utilization:
        total += import_utilization(args.utilization)

    logger.log(f"导入完成，共 {total} 条记录")


if __name__ == "__main__":
    main()
