#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AKShare 互动平台数据下载器
功能：从高水位线开始增量下载深交所互动易和上证 e 互动的投资者问答数据

数据源:
- 深交所互动易 (irm.cninfo.com.cn) - 通过 AKShare stock_irm_cninfo
- 上证 e 互动 (sns.sseinfo.com) - 通过 AKShare stock_sns_sseinfo

独立存储：
- SQLite: ak_irm_history 表
- 文件存储：data/ak_irm/
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
ATTACHMENT_DIR = os.path.join(DATA_DIR, "ak_irm")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

# 默认起始日期
DEFAULT_START_DATE = "2024-01-01"

# 非法文件名字符
ILLEGAL_CHARS = r'[\\/:*?"<>|]'

# 平台配置
PLATFORMS = {
    "hdy": {
        "name": "互动易（深市）",
        "api_func": "stock_irm_cninfo",
        "file_prefix": "HDY",
    },
    "ehd": {
        "name": "e 互动（沪市）",
        "api_func": "stock_sns_sseinfo",
        "file_prefix": "EHD",
    },
}

# ============== e 互动 API 可用性检测 ==============
def check_ehd_api_available():
    """
    检测上证 e 互动 API 是否可用
    返回：(是否可用，原因)
    """
    import warnings
    warnings.filterwarnings('ignore')

    try:
        # 测试一只沪市股票
        df = ak.stock_sns_sseinfo(symbol='600519')
        if df is not None and len(df) > 0:
            return True, "API 正常"
        else:
            return False, "API 返回空数据"
    except Exception as e:
        return False, f"API 调用失败：{e}"


# ============== 日志工具 ==============
class Logger:
    """日志记录器"""

    def __init__(self, log_path):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, message, level="INFO"):
        """写入日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [AK_IRM] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# 全局日志实例
logger = None


# ============== 数据库操作 ==============
def init_database():
    """初始化 SQLite 数据库，创建 AKShare 互动平台历史记录表"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ak_irm_history'")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        # AKShare 互动平台历史表
        cursor.execute('''
            CREATE TABLE ak_irm_history (
                ticker TEXT NOT NULL,
                platform TEXT NOT NULL,
                last_question_date TEXT NOT NULL,
                updated_at TEXT,
                PRIMARY KEY (ticker, platform)
            )
        ''')
        conn.commit()
        logger.log(f"数据库表创建：ak_irm_history")
    else:
        logger.log(f"数据库表已存在：ak_irm_history")

    conn.close()
    logger.log(f"数据库初始化完成：{DB_PATH}")


def get_last_question_date(ticker, platform):
    """获取某只股票上次抓取的日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_question_date FROM ak_irm_history WHERE ticker = ? AND platform = ?",
        (ticker, platform)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return DEFAULT_START_DATE


def update_last_question_date(ticker, platform, question_date):
    """更新某只股票最后抓取日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO ak_irm_history (ticker, platform, last_question_date, updated_at)
        VALUES (?, ?, ?, ?)
    """,
        (ticker, platform, question_date, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
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
    """清理 HTML 标签"""
    if pd.isna(text):
        return ""
    text = str(text)
    return re.sub(r'<[^>]+>', '', text)


def fetch_hdy_questions(stock_code, start_date):
    """
    使用 AKShare 获取深交所互动易问答记录

    Args:
        stock_code: 6 位股票代码
        start_date: 开始日期 YYYY-MM-DD

    Returns:
        DataFrame: 问答记录
    """
    try:
        df = ak.stock_irm_cninfo(symbol=stock_code)

        if df is None or df.empty:
            if logger:
                logger.log(f"  无数据返回", "WARNING")
            return pd.DataFrame()

        if logger:
            logger.log(f"  获取到 {len(df)} 条记录")

        # 过滤有回答的记录
        if '回答内容' in df.columns:
            df = df[df['回答内容'].notna()]

        # 日期过滤
        if '回答时间' in df.columns and not df.empty:
            df = df[df['回答时间'].notna()]
            df['date'] = pd.to_datetime(df['回答时间']).dt.strftime('%Y-%m-%d')
            df = df[df['date'] >= start_date]

        return df

    except Exception as e:
        if logger:
            logger.log(f"AkShare 获取互动易数据失败：{e}", "ERROR")
        return pd.DataFrame()


def fetch_ehd_questions(stock_code, start_date):
    """
    使用 AKShare 获取上证 e 互动问答记录

    Args:
        stock_code: 6 位股票代码
        start_date: 开始日期 YYYY-MM-DD

    Returns:
        DataFrame: 问答记录
    """
    try:
        df = ak.stock_sns_sseinfo(symbol=stock_code)

        if df is None or df.empty:
            if logger:
                logger.log(f"  无数据返回", "WARNING")
            return pd.DataFrame()

        if logger:
            logger.log(f"  获取到 {len(df)} 条记录")

        # 日期过滤
        if '回答时间' in df.columns and not df.empty:
            df = df[df['回答时间'].notna()]
            df['date'] = pd.to_datetime(df['回答时间']).dt.strftime('%Y-%m-%d')
            df = df[df['date'] >= start_date]
        elif '问题时间' in df.columns and not df.empty:
            df = df[df['问题时间'].notna()]
            df['date'] = pd.to_datetime(df['问题时间']).dt.strftime('%Y-%m-%d')
            df = df[df['date'] >= start_date]

        return df

    except Exception as e:
        if logger:
            logger.log(f"AkShare 获取 e 互动数据失败：{e}", "ERROR")
        return pd.DataFrame()


def save_qa_file(filepath, question, answer, publish_date, platform, record=None):
    """
    保存问答记录到文件

    Args:
        filepath: 保存路径
        question: 问题内容
        answer: 回答内容
        publish_date: 发布日期
        platform: 平台标识 (hdy/ehd)
        record: 完整记录（可选）

    Returns:
        bool: 是否保存成功
    """
    try:
        platform_name = "互动易" if platform == "hdy" else "e 互动"

        content = f"""{platform_name}投资者问答记录
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
            for col in ['问题来源', '回答者', '用户名', '行业']:
                if col in record and pd.notna(record[col]):
                    extra_info.append(f"{col}: {record[col]}")
            if extra_info:
                content += "\n".join(extra_info) + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    except Exception as e:
        logger.log(f"保存文件失败：{e}", "ERROR")
        return False


def process_stock(ticker, company_name, stock_code, exchange, platform, attachment_dir):
    """
    处理单只股票

    Returns:
        int: 保存的记录数
    """
    # 创建公司专属文件夹
    safe_company_name = clean_filename(company_name)
    platform_dir = os.path.join(attachment_dir, platform)
    company_dir = os.path.join(platform_dir, f"{ticker}_{safe_company_name}")
    os.makedirs(company_dir, exist_ok=True)

    # 获取上次同步日期
    last_date = get_last_question_date(ticker, platform)

    logger.log(f"[{ticker}] {company_name} ({PLATFORMS[platform]['name']})")

    # 获取记录
    if platform == "hdy":
        records = fetch_hdy_questions(stock_code, last_date)
    else:
        records = fetch_ehd_questions(stock_code, last_date)

    if records.empty:
        logger.log(f"  无新数据")
        return 0

    logger.log(f"  发现 {len(records)} 条新问答")

    # 保存问答记录
    latest_date = last_date
    saved_count = 0

    for index, record in records.iterrows():
        question = clean_html_tags(record.get('问题', ''))

        # 获取回答内容（不同平台字段可能不同）
        answer = ""
        if '回答内容' in record:
            answer = clean_html_tags(record.get('回答内容', ''))
        elif '回答' in record:
            answer = clean_html_tags(record.get('回答', ''))

        # 获取时间
        publish_date = "unknown"
        for time_col in ['回答时间', '问题时间', '提问时间']:
            if time_col in record and pd.notna(record[time_col]):
                publish_date = str(record[time_col])[:10]
                break

        # 生成文件名
        safe_question = clean_filename(question[:50]) if question else "无标题"
        prefix = PLATFORMS[platform]['file_prefix']
        filename = f"{prefix}_{publish_date}_{safe_question}.txt"
        filepath = os.path.join(company_dir, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            saved_count += 1
            continue

        # 保存问答记录到文件
        success = save_qa_file(filepath, question, answer, publish_date, platform, record)

        if success:
            saved_count += 1
            if publish_date > latest_date:
                latest_date = publish_date

    # 更新数据库
    if saved_count > 0:
        update_last_question_date(ticker, platform, latest_date)
        logger.log(f"  保存 {saved_count} 条问答")

    return saved_count


def process_all_stocks(df, attachment_dir, skip_ehd=False):
    """
    逐只股票处理下载

    Args:
        df: 公司列表 DataFrame
        attachment_dir: 附件保存根目录
        skip_ehd: 是否跳过 e 互动（沪市）

    Returns:
        dict: 统计结果
    """
    stats = {
        "hdy": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
        "ehd": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
    }

    total = len(df)

    for idx, row in df.iterrows():
        ticker = row["ticker"]
        company_name = row["company_name"]
        exchange = row["exchange"]

        # 解析股票代码
        parts = ticker.split(".")
        if len(parts) != 2:
            logger.log(f"跳过无效的股票代码格式：{ticker}", "WARNING")
            continue

        stock_code = parts[1]

        try:
            # 根据交易所选择平台
            if exchange == "sz":
                # 深市 - 互动易（API 正常）
                stats["hdy"]["processed"] += 1
                downloaded = process_stock(ticker, company_name, stock_code, exchange, "hdy", attachment_dir)
                if downloaded == 0:
                    stats["hdy"]["no_data"] += 1
                stats["hdy"]["downloaded"] += downloaded

            elif exchange == "sh":
                # 沪市 - e 互动
                if skip_ehd:
                    logger.log(f"跳过 {ticker}：e 互动 API 不可用", "WARNING")
                    stats["ehd"]["failed"] += 1
                else:
                    stats["ehd"]["processed"] += 1
                    downloaded = process_stock(ticker, company_name, stock_code, exchange, "ehd", attachment_dir)
                    if downloaded == 0:
                        stats["ehd"]["no_data"] += 1
                    stats["ehd"]["downloaded"] += downloaded

            else:
                # 北交所 - 无互动平台
                logger.log(f"跳过 {ticker}：不支持的交易所 {exchange}", "WARNING")

        except Exception as e:
            logger.log(f"[{ticker}] 处理失败：{e}", "ERROR")
            if exchange == "sz":
                stats["hdy"]["failed"] += 1
            elif exchange == "sh":
                stats["ehd"]["failed"] += 1

        # 进度汇报
        current = stats["hdy"]["processed"] + stats["ehd"]["processed"]
        if current % 10 == 0:
            total_downloaded = stats["hdy"]["downloaded"] + stats["ehd"]["downloaded"]
            logger.log(f"--- 进度：{current}/{total} | 已下载：{total_downloaded} 条 ---")

        # 反爬休眠
        time.sleep(random.uniform(0.5, 1.5))

    return stats


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
    print("AKShare 互动平台数据下载器")
    print("支持：深交所互动易 + 上证 e 互动")
    print("=" * 60)

    # 初始化日志
    logger = Logger(LOG_PATH)
    logger.log("程序启动")

    # 初始化
    init_database()
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    # 检测 e 互动 API 可用性
    logger.log("正在检测 e 互动 API 可用性...")
    ehd_available, ehd_reason = check_ehd_api_available()
    if ehd_available:
        logger.log("e 互动 API 可用，将同时下载沪市数据")
    else:
        logger.log(f"e 互动 API 不可用：{ehd_reason}", "WARNING")
        logger.log("将跳过沪市股票（可在中国大陆网络环境下重试）", "WARNING")

    # 加载公司列表
    df = load_company_list()

    # 统计各交易所数量
    exchange_counts = df['exchange'].value_counts()
    logger.log(f"交易所分布：{dict(exchange_counts)}")

    # 逐只股票处理
    stats = process_all_stocks(df, ATTACHMENT_DIR, skip_ehd=not ehd_available)

    # 最终统计
    logger.log("\n" + "=" * 60)
    logger.log("下载任务完成")
    logger.log("=" * 60)

    logger.log("\n【互动易 - 深市】")
    logger.log(f"  处理公司数：{stats['hdy']['processed']}")
    logger.log(f"  无数据公司数：{stats['hdy']['no_data']}")
    logger.log(f"  失败公司数：{stats['hdy']['failed']}")
    logger.log(f"  成功下载：{stats['hdy']['downloaded']} 条问答")

    logger.log("\n【e 互动 - 沪市】")
    logger.log(f"  处理公司数：{stats['ehd']['processed']}")
    logger.log(f"  无数据公司数：{stats['ehd']['no_data']}")
    logger.log(f"  失败公司数：{stats['ehd']['failed']}")
    logger.log(f"  成功下载：{stats['ehd']['downloaded']} 条问答")

    logger.log(f"\n保存目录：{ATTACHMENT_DIR}")
    logger.log(f"日志文件：{LOG_PATH}")
    logger.log("=" * 60)


if __name__ == "__main__":
    main()
