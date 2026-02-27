#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上证 e 互动 - 投资者问答数据下载器
功能：从高水位线开始增量下载指定公司的投资者问答数据

数据源：上证 e 互动 (sns.sseinfo.com)
API: https://sns.sseinfo.com/api/answer/list

抓取内容:
1. 投资者提问 & 上市公司董秘回复记录
2. 上市公司投关活动相关公告、业绩说明会实录
3. 上市公司主动发布的投关相关文件
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
ATTACHMENT_DIR = os.path.join(DATA_DIR, "ehd_attachments")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

# 默认起始日期
DEFAULT_START_DATE = "2024-01-01"

# 请求头配置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://sns.sseinfo.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://sns.sseinfo.com",
}

# 非法文件名字符
ILLEGAL_CHARS = r'[\\/:*?"<>|]'

# 市场映射（沪市专用）
MARKET_MAP = {
    "sh": "sse",  # 上交所
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
        log_line = f"[{timestamp}] [EHD] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# 全局日志实例
logger = None


# ============== 数据库操作 ==============
def init_database():
    """初始化 SQLite 数据库，创建 e 互动历史记录表"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # e 互动历史表（沪市）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ehd_history (
            ticker TEXT PRIMARY KEY,
            last_question_date TEXT NOT NULL,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.log(f"数据库初始化完成：{DB_PATH} (ehd_history 表)")


def get_last_question_date(ticker):
    """获取某只股票上次抓取的日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_question_date FROM ehd_history WHERE ticker = ?", (ticker,)
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
        INSERT OR REPLACE INTO ehd_history (ticker, last_question_date, updated_at)
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
    # 只保留沪市股票
    df_sh = df[df['exchange'] == 'sh'].copy()
    logger.log(f"加载公司列表，共 {len(df_sh)} 家沪市公司")
    return df_sh


def clean_html_tags(text):
    """清理 HTML 标签（如 <em>）"""
    return re.sub(r'<[^>]+>', '', text)


def fetch_questions_for_stock(stock_code, start_date, end_date=None):
    """
    获取单只股票的投资者问答记录

    API 端点：https://sns.sseinfo.com/api/answer/list

    Args:
        stock_code: 6 位股票代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD，默认今天

    Returns:
        list: 记录列表
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    session = requests.Session()
    try:
        session.get("https://sns.sseinfo.com/", headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException:
        pass

    url = "https://sns.sseinfo.com/api/answer/list"

    PAGE_SIZE = 30
    all_records = []
    page_num = 1

    try:
        while True:
            # 构建查询参数
            params = {
                "stockcode": stock_code,
                "pageSize": str(PAGE_SIZE),
                "pageNum": str(page_num),
                "startDate": start_date,
                "endDate": end_date,
            }

            response = session.get(url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # 检查是否有数据
            answers = data.get("data", []) or data.get("answers", []) or data.get("list", [])
            if not answers:
                break

            # 处理当前页的记录
            for a in answers:
                question_text = a.get("questionText", "") or a.get("question", "") or a.get("content", "")
                answer_text = a.get("answerText", "") or a.get("answer", "") or a.get("reply", "")

                # 获取时间戳
                timestamp = a.get("questionTime", 0) or a.get("askTime", 0) or a.get("create_time", 0)
                if timestamp:
                    if isinstance(timestamp, (int, float)):
                        publish_date = datetime.fromtimestamp(
                            int(timestamp) / 1000
                        ).strftime("%Y-%m-%d")
                    else:
                        publish_date = str(timestamp)[:10]
                else:
                    publish_date = "unknown"

                all_records.append(
                    {
                        "question": clean_html_tags(question_text),
                        "answer": clean_html_tags(answer_text),
                        "publishDate": publish_date,
                        "timestamp": timestamp,
                    }
                )

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
    failed_stocks = []  # 记录失败的股票

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

        # 获取记录
        try:
            records = fetch_questions_for_stock(stock_code, last_date)
        except Exception as e:
            logger.log(f"[{ticker}] 查询失败：{e}", "ERROR")
            failed_count += 1
            failed_stocks.append(f"{ticker} {company_name} (查询失败)")
            continue

        # 过滤日期
        records = [r for r in records if r["publishDate"] > last_date]

        logger.log(f"  发现 {len(records)} 条新问答")

        if not records:
            no_data_count += 1
            continue

        # 保存问答记录
        latest_date = last_date
        saved_count = 0

        for record in records:
            question = record["question"]
            answer = record["answer"]
            publish_date = record["publishDate"]

            # 生成文件名
            safe_question = clean_filename(question[:50])
            filename = f"{publish_date}_{safe_question}.txt"
            filepath = os.path.join(company_dir, filename)

            # 检查文件是否已存在
            if os.path.exists(filepath):
                logger.log(f"  [跳过] 文件已存在")
                saved_count += 1
                continue

            # 保存问答记录到文件
            success = save_qa_file(filepath, question, answer, publish_date)

            if success:
                logger.log(f"  [成功] {safe_question[:40]}...")
                saved_count += 1
                if publish_date > latest_date:
                    latest_date = publish_date
            else:
                logger.log(f"  [失败] {safe_question[:40]}...", "ERROR")

            # 反爬休眠（2-5 秒）
            time.sleep(random.uniform(2, 5))

        # 更新数据库
        if saved_count > 0:
            update_last_question_date(ticker, latest_date)
            logger.log(f"[{ticker}] 完成：保存 {saved_count} 条问答")

        total_downloaded += saved_count

        # 进度汇报
        if processed_count % 10 == 0:
            logger.log(f"--- 进度：{processed_count}/{len(df)} | 已下载：{total_downloaded} 条 ---")

        # 每只股票查询后休眠，避免请求过快
        time.sleep(random.uniform(1, 3))

    # 输出失败列表
    if failed_stocks:
        logger.log("\n=== 失败股票列表 ===", "WARNING")
        for stock in failed_stocks:
            logger.log(f"  - {stock}", "WARNING")

    return total_downloaded, processed_count, no_data_count, failed_count


def save_qa_file(filepath, question, answer, publish_date):
    """
    保存问答记录到文件

    Args:
        filepath: 保存路径
        question: 问题内容
        answer: 回答内容
        publish_date: 发布日期

    Returns:
        bool: 是否保存成功
    """
    try:
        content = f"""e 互动投资者问答记录
=====================================
日期：{publish_date}

【投资者提问】
{question}

【董秘回复】
{answer}

=====================================
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    except Exception:
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
    print("上证 e 互动 - 投资者问答数据下载器")
    print("=" * 60)

    # 初始化日志
    logger = Logger(LOG_PATH)
    logger.log("程序启动")

    # 初始化
    init_database()
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    # 加载公司列表（只保留沪市）
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
