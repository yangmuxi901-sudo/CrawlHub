#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股投资者关系活动记录表 PDF 下载器（独立版）
功能：从高水位线开始增量下载指定公司的投资者关系活动记录表 PDF

数据源：巨潮资讯网 (www.cninfo.com.cn)
API: http://www.cninfo.com.cn/new/hisAnnouncement/query

修复说明：
1. 改为逐只股票查询，添加正确的 stock、plate 参数
2. 使用 JSON 映射表获取 orgId（从 https://www.cninfo.com.cn/new/data/szse_stock.json）
3. 根据 exchange 选择正确的 tabName
4. 修改文件保存结构：每家公司单独一个文件夹
5. 添加详细日志
"""

import os
import re
import sys
import time
import random
import sqlite3
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import quote

# ============== 配置常量 ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PDF_DIR = os.path.join(DATA_DIR, "ir_pdfs")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

# 默认起始日期
DEFAULT_START_DATE = "2024-01-01"

# 请求头配置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "http://www.cninfo.com.cn/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# 非法文件名字符
ILLEGAL_CHARS = r'[\\/:*?"<>|]'

# 市场映射
MARKET_MAP = {
    "sz": "szse",  # 深交所
    "sh": "sse",   # 上交所
    "bj": "bse",   # 北交所
}

# plate 参数映射
PLATE_MAP = {
    "sz": "sz",
    "sh": "sh",
    "bj": "bj",
}


# ============== 日志工具 ==============
class Logger:
    """日志记录器"""

    def __init__(self, log_path):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, message, level="INFO"):
        """写入日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# 全局日志实例
logger = None

# orgId 映射表缓存
ORGID_MAPPING = {}


# ============== orgId 映射表 ==============
def load_orgid_mapping():
    """
    从巨潮资讯网下载 orgId 映射表

    Returns:
        bool: 是否加载成功
    """
    global ORGID_MAPPING
    url = "https://www.cninfo.com.cn/new/data/szse_stock.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        ORGID_MAPPING = {s['code']: s['orgId'] for s in data.get('stockList', [])}
        print(f"[系统] 加载 orgId 映射表完成，共 {len(ORGID_MAPPING)} 条记录")
        return True
    except Exception as e:
        print(f"[错误] 加载 orgId 映射表失败：{e}")
        return False


def get_orgid(stock_code):
    """
    获取股票的 orgId

    Args:
        stock_code: 6位股票代码

    Returns:
        str or None: orgId，如果未找到返回 None
    """
    return ORGID_MAPPING.get(stock_code)


def get_tab_name(exchange):
    """
    根据交易所获取正确的 tabName 参数

    Args:
        exchange: 交易所代码 (sz/sh/bj)

    Returns:
        str: tabName 参数值
    """
    if exchange == "sz":
        return "relation"  # 深圳用 relation
    elif exchange == "sh":
        return "fulltext"  # 上海可能用 fulltext
    elif exchange == "bj":
        return "relation"  # 北京用 relation
    else:
        return "relation"


# ============== 数据库操作 ==============
def init_database():
    """初始化 SQLite 数据库，创建下载历史记录表"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_history (
            ticker TEXT PRIMARY KEY,
            last_publish_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.log(f"数据库初始化完成：{DB_PATH}")


def get_last_publish_date(ticker):
    """获取某只股票上次抓取的日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_publish_date FROM download_history WHERE ticker = ?", (ticker,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return DEFAULT_START_DATE


def update_last_publish_date(ticker, publish_date):
    """更新某只股票最后抓取日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO download_history (ticker, last_publish_date)
        VALUES (?, ?)
    """,
        (ticker, publish_date),
    )
    conn.commit()
    conn.close()


# ============== 数据获取 ==============
def load_company_list():
    """加载公司列表 CSV"""
    if not os.path.exists(COMPANY_LIST_PATH):
        logger.log(f"未找到公司列表文件：{COMPANY_LIST_PATH}", "ERROR")
        sys.exit(1)

    df = pd.read_csv(COMPANY_LIST_PATH)
    logger.log(f"加载公司列表，共 {len(df)} 家公司")
    return df


def clean_html_tags(text):
    """清理 HTML 标签（如 <em>）"""
    return re.sub(r'<[^>]+>', '', text)


def fetch_ir_records_for_stock(stock_code, org_id, exchange, start_date, end_date=None):
    """
    获取单只股票的投资者关系记录

    Args:
        stock_code: 6位股票代码
        org_id: 机构ID
        exchange: 交易所代码 (sz/sh/bj)
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD，默认今天

    Returns:
        list: 记录列表
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    session = requests.Session()
    try:
        session.get("http://www.cninfo.com.cn/", headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        pass

    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    # 获取正确的参数
    market = MARKET_MAP.get(exchange, "szse")
    plate = PLATE_MAP.get(exchange, "")
    tab_name = get_tab_name(exchange)

    # 上海股票需要搜索关键词过滤
    search_key = "投资者关系" if exchange == "sh" else ""

    # 构建查询参数
    # stock 参数格式：股票代码,orgId
    stock_param = f"{stock_code},{org_id}" if org_id else stock_code

    PAGE_SIZE = 30
    all_records = []
    total_count = 0
    page_num = 1

    try:
        while True:
            params = {
                "stock": stock_param,          # 股票代码,orgId
                "tabName": tab_name,           # 根据交易所选择
                "pageSize": str(PAGE_SIZE),
                "pageNum": str(page_num),
                "column": market,              # 市场 (szse/sse/bse)
                "category": "",
                "plate": plate,                # 板块 (sz/sh/bj)
                "seDate": f"{start_date}~{end_date}",
                "searchkey": search_key,       # 上海股票需要搜索关键词
                "secid": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            }

            response = session.post(url, headers=HEADERS, data=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # 获取总数（仅第一页）
            if page_num == 1:
                total_count = data.get("totalAnnouncement", 0)
                if total_count == 0:
                    return []

            announcements = data.get("announcements", [])
            if not announcements:
                break

            # 处理当前页的记录
            for ann in announcements:
                title = ann.get("announcementTitle", "")
                title_clean = clean_html_tags(title)

                timestamp = ann.get("announcementTime", 0)
                if timestamp:
                    publish_date = datetime.fromtimestamp(
                        int(timestamp) / 1000
                    ).strftime("%Y-%m-%d")
                else:
                    publish_date = "unknown"

                all_records.append(
                    {
                        "title": title_clean,
                        "publishDate": publish_date,
                        "timestamp": timestamp,
                        "pdfUrl": f"http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}",
                    }
                )

            # 检查是否还有更多页
            fetched = page_num * PAGE_SIZE
            if fetched >= total_count:
                break

            page_num += 1
            # 反爬休眠
            time.sleep(random.uniform(0.3, 0.8))

        return all_records

    except requests.exceptions.Timeout:
        logger.log(f"股票 {stock_code} 请求超时", "WARNING")
        return []
    except requests.exceptions.RequestException as e:
        logger.log(f"股票 {stock_code} 网络错误：{e}", "WARNING")
        return []
    except Exception as e:
        logger.log(f"股票 {stock_code} 解析失败：{e}", "WARNING")
        return []


def process_all_stocks(df, pdf_dir):
    """
    逐只股票处理下载

    Args:
        df: 公司列表 DataFrame
        pdf_dir: PDF 保存根目录

    Returns:
        tuple: (成功下载数, 处理公司数, 无数据公司数, 失败公司数)
    """
    total_downloaded = 0
    processed_count = 0
    no_data_count = 0
    failed_count = 0
    failed_stocks = []  # 记录失败的股票

    for idx, row in df.iterrows():
        processed_count += 1
        ticker = row["ticker"]
        company_name = row["company_name"]
        exchange = row["exchange"]

        # 解析股票代码
        parts = ticker.split(".")
        if len(parts) != 2:
            logger.log(f"跳过无效的股票代码格式：{ticker}", "WARNING")
            failed_count += 1
            failed_stocks.append(f"{ticker} (格式错误)")
            continue

        stock_code = parts[1]

        # 获取 orgId
        org_id = get_orgid(stock_code)
        if not org_id:
            logger.log(f"跳过 {ticker}：在映射表中未找到 orgId", "WARNING")
            failed_count += 1
            failed_stocks.append(f"{ticker} {company_name} (无orgId)")
            continue

        # 创建公司专属文件夹
        safe_company_name = clean_filename(company_name)
        company_dir = os.path.join(pdf_dir, f"{ticker}_{safe_company_name}")
        os.makedirs(company_dir, exist_ok=True)

        # 获取上次同步日期
        last_date = get_last_publish_date(ticker)

        logger.log(f"[{processed_count}/{len(df)}] 查询 {ticker} {company_name} ({exchange}) orgId={org_id}")

        # 获取记录
        try:
            records = fetch_ir_records_for_stock(
                stock_code, org_id, exchange, last_date
            )
        except Exception as e:
            logger.log(f"[{ticker}] 查询失败：{e}", "ERROR")
            failed_count += 1
            failed_stocks.append(f"{ticker} {company_name} (查询失败)")
            continue

        # 过滤日期
        records = [r for r in records if r["publishDate"] > last_date]

        logger.log(f"  发现 {len(records)} 份新纪要")

        if not records:
            no_data_count += 1
            continue

        # 下载 PDF
        downloaded_count = 0
        latest_date = last_date

        for record in records:
            title = record["title"]
            publish_date = record["publishDate"]
            pdf_url = record["pdfUrl"]

            # 清洗标题
            clean_title = clean_filename(title)

            # 生成文件名
            filename = f"{publish_date}_{clean_title}.pdf"
            filepath = os.path.join(company_dir, filename)

            # 检查文件是否已存在
            if os.path.exists(filepath):
                logger.log(f"  [跳过] 文件已存在")
                downloaded_count += 1
                # 更新最新日期，确保高水位线推进
                if publish_date > latest_date:
                    latest_date = publish_date
                continue

            # 下载 PDF
            success = download_pdf(pdf_url, filepath)

            if success:
                logger.log(f"  [成功] {clean_title[:40]}...")
                downloaded_count += 1
                if publish_date > latest_date:
                    latest_date = publish_date
            else:
                logger.log(f"  [失败] {clean_title[:40]}...", "ERROR")

            # 反爬休眠（2-5秒）
            time.sleep(random.uniform(2, 5))

        # 更新数据库
        if downloaded_count > 0:
            update_last_publish_date(ticker, latest_date)
            logger.log(f"[{ticker}] 完成：下载 {downloaded_count} 份文件")

        total_downloaded += downloaded_count

        # 进度汇报
        if processed_count % 10 == 0:
            logger.log(f"--- 进度：{processed_count}/{len(df)} | 已下载：{total_downloaded} 份 ---")

        # 每只股票查询后休眠，避免请求过快
        time.sleep(random.uniform(1, 3))

    # 输出失败列表
    if failed_stocks:
        logger.log("\n=== 失败股票列表 ===", "WARNING")
        for stock in failed_stocks:
            logger.log(f"  - {stock}", "WARNING")

    return total_downloaded, processed_count, no_data_count, failed_count


def download_pdf(url, filepath, max_retries=3):
    """
    下载 PDF 文件（带重试机制）

    Args:
        url: PDF 下载地址
        filepath: 保存路径
        max_retries: 最大重试次数，默认 3 次

    Returns:
        bool: 是否下载成功
    """
    base_delay = 2  # 基础等待时间（秒）

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15, stream=True)

            # 针对 403/502/503 等状态码重试
            if response.status_code in [403, 502, 503, 504]:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                    continue
                else:
                    return False

            response.raise_for_status()

            # 写入文件
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return True

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return False
        except requests.exceptions.HTTPError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return False
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return False
        except Exception:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            return False

    return False


def clean_filename(title):
    """清洗标题中的非法字符"""
    # 移除非法字符
    cleaned = re.sub(ILLEGAL_CHARS, "_", title)
    # 移除多余空格
    cleaned = " ".join(cleaned.split())
    # 限制长度（避免路径过长）
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned.strip()


def main():
    """主函数"""
    global logger

    print("=" * 60)
    print("A 股投资者关系活动记录表 PDF 下载器（修复版）")
    print("=" * 60)

    # 初始化日志
    logger = Logger(LOG_PATH)
    logger.log("程序启动")

    # 加载 orgId 映射表
    if not load_orgid_mapping():
        logger.log("orgId 映射表加载失败，程序退出", "ERROR")
        sys.exit(1)
    logger.log(f"orgId 映射表加载成功，共 {len(ORGID_MAPPING)} 条记录")

    # 初始化
    init_database()
    os.makedirs(PDF_DIR, exist_ok=True)

    # 加载公司列表
    df = load_company_list()

    # 统计各交易所数量
    exchange_counts = df['exchange'].value_counts()
    logger.log(f"交易所分布：{dict(exchange_counts)}")

    # 逐只股票处理
    total_downloaded, processed_count, no_data_count, failed_count = process_all_stocks(df, PDF_DIR)

    # 最终统计
    logger.log("\n" + "=" * 60)
    logger.log("下载任务完成")
    logger.log(f"处理公司数：{processed_count}")
    logger.log(f"无数据公司数：{no_data_count}")
    logger.log(f"失败公司数：{failed_count}")
    logger.log(f"成功下载：{total_downloaded} 份 PDF")
    logger.log(f"保存目录：{PDF_DIR}")
    logger.log(f"日志文件：{LOG_PATH}")
    logger.log("=" * 60)


if __name__ == "__main__":
    main()
