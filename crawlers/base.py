#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
化工爬虫基类
提供日志、数据库、反爬、HTTP请求等公共能力
"""

import os
import re
import time
import random
import sqlite3
import yaml
import requests
import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod


# ============== 配置常量 ==============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "chemical_crawler.log")

# 确保目录存在
for d in [CONFIG_DIR, DATA_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ============== 日志工具 ==============
class Logger:
    """日志记录器，兼容项目已有风格"""

    def __init__(self, log_path=LOG_PATH, tag="CHEMICAL"):
        self.log_path = log_path
        self.tag = tag
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{self.tag}] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# ============== 产品配置加载 ==============
def load_products_config(config_path=None):
    """加载 products.yaml 配置"""
    if config_path is None:
        config_path = os.path.join(CONFIG_DIR, "products.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============== 数据库操作 ==============
def init_chemical_db():
    """初始化化工数据相关表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 化工价格爬取历史
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemical_crawl_history (
            product_name TEXT NOT NULL,
            crawl_type TEXT NOT NULL,
            last_crawl_date TEXT NOT NULL,
            updated_at TEXT,
            PRIMARY KEY (product_name, crawl_type)
        )
    """)

    # industry_metrics 表（供 AI Hedge Fund 使用）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS industry_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            trade_date TEXT,
            industry TEXT DEFAULT '化工',
            product_spread REAL,
            spread_percentile REAL,
            capacity_utilization REAL,
            inventory_days REAL,
            product_price REAL,
            price_change REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, trade_date, industry)
        )
    """)

    conn.commit()
    conn.close()

def get_last_crawl_date(product_name, crawl_type="price"):
    """获取某产品上次爬取日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_crawl_date FROM chemical_crawl_history WHERE product_name=? AND crawl_type=?",
        (product_name, crawl_type)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def update_crawl_date(product_name, crawl_type, date_str):
    """更新某产品的爬取日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO chemical_crawl_history (product_name, crawl_type, last_crawl_date, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(product_name, crawl_type) DO UPDATE SET
            last_crawl_date=excluded.last_crawl_date,
            updated_at=excluded.updated_at
    """, (product_name, crawl_type, date_str, now))
    conn.commit()
    conn.close()


# ============== 爬虫基类 ==============
class BaseCrawler(ABC):
    """化工数据爬虫基类"""

    def __init__(self, name="BaseCrawler"):
        self.name = name
        self.logger = Logger(tag=name)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.config = load_products_config()
        init_chemical_db()

    def sleep(self, min_sec=2, max_sec=5):
        """反爬随机延迟"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def safe_request(self, url, method="GET", max_retries=3, **kwargs):
        """带重试的安全请求"""
        kwargs.setdefault("timeout", 15)
        for attempt in range(1, max_retries + 1):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, **kwargs)
                else:
                    resp = self.session.post(url, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                self.logger.log(f"请求失败 (第{attempt}次): {url} - {e}", "WARNING")
                if attempt < max_retries:
                    self.sleep(1, 3)
        self.logger.log(f"请求最终失败: {url}", "ERROR")
        return None

    def validate_price(self, price, product_name=""):
        """校验价格数据合理性"""
        if price is None or price < 0:
            self.logger.log(f"异常价格: {product_name} = {price}", "WARNING")
            return False
        if price > 500000:
            self.logger.log(f"价格异常偏高: {product_name} = {price}", "WARNING")
            return False
        return True

    def validate_rate(self, rate, product_name=""):
        """校验开工率数据合理性"""
        if rate is None or rate < 0 or rate > 100:
            self.logger.log(f"异常开工率: {product_name} = {rate}%", "WARNING")
            return False
        return True

    @abstractmethod
    def crawl(self):
        """子类实现具体爬取逻辑，返回 DataFrame"""
        pass

    def run(self):
        """统一运行入口"""
        self.logger.log(f"{'='*60}")
        self.logger.log(f"{self.name} 开始运行")
        self.logger.log(f"{'='*60}")
        try:
            df = self.crawl()
            if df is not None and not df.empty:
                self.logger.log(f"爬取完成，共 {len(df)} 条数据")
                return df
            else:
                self.logger.log("未获取到数据", "WARNING")
                return pd.DataFrame()
        except Exception as e:
            self.logger.log(f"爬取异常: {e}", "ERROR")
            return pd.DataFrame()
