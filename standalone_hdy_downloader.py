#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深交所互动易 - 投资者问答数据下载器 (AkShare 版)
功能：从高水位线开始增量下载指定公司的投资者问答数据

数据源：深交所互动易 (irm.cninfo.com.cn)
通过 AkShare 库获取数据
"""

import os
import re
import sys
import time
import random
import sqlite3
import pandas as pd
from datetime import datetime

try:
    import akshare as ak
except ImportError:
    print("错误：需要安装 akshare 库，请运行：pip install akshare")
    sys.exit(1)

# ============== 配置常量 ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ATTACHMENT_DIR = os.path.join(DATA_DIR, "hdy_attachments")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

# 默认起始日期
DEFAULT_START_DATE = "2024-01-01"

# 非法文件名字符
ILLEGAL_CHARS = r'[\\/:*?"<>|]'


# ============== 日志工具 ==============
class Logger:
    """日志记录器"""

    def __init__(self, log_path):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, message, level="INFO"):
        """写入日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [HDY] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# 全局日志实例
logger = None


# ============== 数据库操作 ==============
def init_database():
    """初始化 SQLite 数据库，创建互动易历史记录表"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 互动易历史表（深市）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hdy_history (
            ticker TEXT PRIMARY KEY,
            last_question_date TEXT NOT NULL,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.log(f"数据库初始化完成：{DB_PATH} (hdy_history 表)")


def get_last_question_date(ticker):
    """获取某只股票上次抓取的日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_question_date FROM hdy_history WHERE ticker = ?", (ticker,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return DEFAULT_START_DATE


def update_last_question_date(ticker, question_date):
    """更新某只股票最后抓取日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO hdy_history (ticker, last_question_date, updated_at)
        VALUES (?, ?, ?)
    """,
        (ticker, question_date, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
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
    # 只保留深市股票
    df_sz = df[df['exchange'] == 'sz'].copy()
    logger.log(f"加载公司列表，共 {len(df_sz)} 家深市公司")
    return df_sz


def clean_html_tags(text):
    """清理 HTML 标签"""
    if pd.isna(text):
        return ""
    text = str(text)
    return re.sub(r'<[^>]+>', '', text)


def fetch_questions_for_stock(stock_code, start_date):
    """
    使用 AkShare 获取单只股票的投资者问答记录

    Args:
        stock_code: 6 位股票代码
        start_date: 开始日期 YYYY-MM-DD

    Returns:
        DataFrame: 问答记录
    """
    try:
        # 使用 AkShare 获取互动易数据
        df = ak.stock_irm_cninfo(symbol=stock_code)

        if df is None or df.empty:
            logger.log(f"  AkShare 无数据返回", "WARNING")
            return pd.DataFrame()

        logger.log(f"  AkShare 获取到 {len(df)} 条记录")

        # 过滤日期
        if '回答时间' in df.columns:
            # 有回答时间的，用回答时间过滤
            df = df[df['回答时间'].notna()]
            if not df.empty:
                df['回答时间'] = pd.to_datetime(df['回答时间']).dt.strftime('%Y-%m-%d')
                df = df[df['回答时间'] >= start_date]
        elif '提问时间' in df.columns:
            # 只有提问时间的，用提问时间过滤
            df = df[df['提问时间'].notna()]
            if not df.empty:
                df['提问时间'] = pd.to_datetime(df['提问时间']).dt.strftime('%Y-%m-%d')
                df = df[df['提问时间'] >= start_date]

        return df

    except Exception as e:
        logger.log(f"AkShare 获取数据失败：{e}", "ERROR")
        return pd.DataFrame()


def process_all_stocks(df, attachment_dir):
    """
    逐只股票处理下载

    Args:
        df: 公司列表 DataFrame
        attachment_dir: 附件保存根目录

    Returns:
        tuple: (成功下载数，处理公司数，无数据公司数，失败公司数)
    """
    total_downloaded = 0
    processed_count = 0
    no_data_count = 0
    failed_count = 0
    failed_stocks = []

    for idx, row in df.iterrows():
        processed_count += 1
        ticker = row["ticker"]
        company_name = row["company_name"]

        # 解析股票代码
        parts = ticker.split(".")
        if len(parts) != 2:
            logger.log(f"跳过无效的股票代码格式：{ticker}", "WARNING")
            failed_count += 1
            failed_stocks.append(f"{ticker} (格式错误)")
            continue

        stock_code = parts[1]

        # 创建公司专属文件夹
        safe_company_name = clean_filename(company_name)
        company_dir = os.path.join(attachment_dir, f"{ticker}_{safe_company_name}")
        os.makedirs(company_dir, exist_ok=True)

        # 获取上次同步日期
        last_date = get_last_question_date(ticker)

        logger.log(f"[{processed_count}/{len(df)}] 查询 {ticker} {company_name}")

        # 获取记录（使用 AkShare）
        try:
            records = fetch_questions_for_stock(stock_code, last_date)
        except Exception as e:
            logger.log(f"[{ticker}] 查询失败：{e}", "ERROR")
            failed_count += 1
            failed_stocks.append(f"{ticker} {company_name} (查询失败)")
            continue

        logger.log(f"  发现 {len(records)} 条新问答")

        if records.empty:
            no_data_count += 1
            continue

        # 保存问答记录
        latest_date = last_date
        saved_count = 0

        for index, record in records.iterrows():
            question = clean_html_tags(record.get('问题', ''))
            answer = clean_html_tags(record.get('回答内容', '') or record.get('回答', ''))

            # 获取时间
            if '回答时间' in record and pd.notna(record['回答时间']):
                publish_date = str(record['回答时间'])[:10]
            elif '提问时间' in record and pd.notna(record['提问时间']):
                publish_date = str(record['提问时间'])[:10]
            else:
                publish_date = "unknown"

            # 生成文件名
            safe_question = clean_filename(question[:50]) if question else "无标题"
            filename = f"{publish_date}_{safe_question}.txt"
            filepath = os.path.join(company_dir, filename)

            # 检查文件是否已存在
            if os.path.exists(filepath):
                logger.log(f"  [跳过] 文件已存在")
                saved_count += 1
                continue

            # 保存问答记录到文件
            success = save_qa_file(filepath, question, answer, publish_date, record)

            if success:
                logger.log(f"  [成功] {safe_question[:40]}...")
                saved_count += 1
                if publish_date > latest_date:
                    latest_date = publish_date
            else:
                logger.log(f"  [失败] {safe_question[:40]}...", "ERROR")

        # 更新数据库
        if saved_count > 0:
            update_last_question_date(ticker, latest_date)
            logger.log(f"[{ticker}] 完成：保存 {saved_count} 条问答")

        total_downloaded += saved_count

        # 进度汇报
        if processed_count % 10 == 0:
            logger.log(f"--- 进度：{processed_count}/{len(df)} | 已下载：{total_downloaded} 条 ---")

    # 输出失败列表
    if failed_stocks:
        logger.log("\n=== 失败股票列表 ===", "WARNING")
        for stock in failed_stocks:
            logger.log(f"  - {stock}", "WARNING")

    return total_downloaded, processed_count, no_data_count, failed_count


def save_qa_file(filepath, question, answer, publish_date, record=None):
    """
    保存问答记录到文件

    Args:
        filepath: 保存路径
        question: 问题内容
        answer: 回答内容
        publish_date: 发布日期
        record: 完整记录（可选）

    Returns:
        bool: 是否保存成功
    """
    try:
        content = f"""互动易投资者问答记录
=====================================
日期：{publish_date}

【投资者提问】
{question if question else '无'}

【董秘回复】
{answer if answer else '无'}

=====================================
"""
        # 添加额外信息
        if record is not None:
            extra_info = []
            if '问题来源' in record and pd.notna(record['问题来源']):
                extra_info.append(f"问题来源：{record['问题来源']}")
            if '回答者' in record and pd.notna(record['回答者']):
                extra_info.append(f"回答者：{record['回答者']}")
            if extra_info:
                content += "\n".join(extra_info) + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    except Exception as e:
        logger.log(f"保存文件失败：{e}", "ERROR")
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
    print("深交所互动易 - 投资者问答数据下载器 (AkShare 版)")
    print("=" * 60)

    # 初始化日志
    logger = Logger(LOG_PATH)
    logger.log("程序启动")

    # 初始化
    init_database()
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    # 加载公司列表（只保留深市）
    df = load_company_list()

    # 逐只股票处理
    total_downloaded, processed_count, no_data_count, failed_count = process_all_stocks(df, ATTACHMENT_DIR)

    # 最终统计
    logger.log("\n" + "=" * 60)
    logger.log("下载任务完成")
    logger.log(f"处理公司数：{processed_count}")
    logger.log(f"无数据公司数：{no_data_count}")
    logger.log(f"失败公司数：{failed_count}")
    logger.log(f"成功下载：{total_downloaded} 条问答")
    logger.log(f"保存目录：{ATTACHMENT_DIR}")
    logger.log(f"日志文件：{LOG_PATH}")
    logger.log("=" * 60)


if __name__ == "__main__":
    main()
