#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
投资者关系活动记录表下载器（原生 requests + 代理池）

功能：从高水位线开始增量下载深交所互动易和上证 e 互动的投资者问答数据

数据源:
- 深交所互动易 (irm.cninfo.com.cn) - 可直连
- 上证 e 互动 (sns.sseinfo.com) - 需要代理

使用方式:
1. 互动易（深市）可直接运行，无需代理
2. e 互动（沪市）需要代理，可选择：
   - 使用免费代理池（成功率较低）
   - 使用付费代理（推荐）
   - 在中国大陆网络环境下运行

安装依赖:
pip install requests pandas beautifulsoup4
"""

import os
import re
import sys
import time
import random
import sqlite3
import pandas as pd
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ============== 配置常量 ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ATTACHMENT_DIR = os.path.join(DATA_DIR, "irm")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

# ============== 免费代理池 ==============
class SimpleProxyPool:
    """免费代理池 - 多源抓取"""

    def __init__(self):
        self.proxies = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # 免费代理源 - 多个来源
        self.proxy_sources = [
            "https://www.kuaidaili.com/free/inha/",
            "https://www.89ip.cn/",
            "https://www.kuaidaili.com/free/intr/",
            "https://www.kuaidaili.com/free/outha/",
        ]
        self.valid_proxies = []

    def fetch_proxies(self):
        """从免费源抓取代理"""
        logger.log("正在抓取免费代理...")

        new_proxies = []

        # 抓取快代理 - 国内高匿代理
        try:
            for page in range(1, 6):
                url = f"https://www.kuaidaili.com/free/inha/{page}/"
                resp = requests.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'html.parser')
                tbody = soup.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            ip = tds[0].text.strip()
                            port = tds[1].text.strip()
                            new_proxies.append(f"http://{ip}:{port}")
        except Exception as e:
            logger.log(f"抓取快代理 (inha) 失败：{e}", "WARNING")

        # 抓取快代理 - 国内普通代理
        try:
            for page in range(1, 6):
                url = f"https://www.kuaidaili.com/free/intr/{page}/"
                resp = requests.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'html.parser')
                tbody = soup.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            ip = tds[0].text.strip()
                            port = tds[1].text.strip()
                            new_proxies.append(f"http://{ip}:{port}")
        except Exception as e:
            logger.log(f"抓取快代理 (intr) 失败：{e}", "WARNING")

        # 抓取 89IP 代理
        try:
            resp = requests.get(self.proxy_sources[1], headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.find_all('div', class_='list-ip-item'):
                text = item.get_text().strip()
                # 提取 IP:port
                import re
                matches = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', text)
                for m in matches:
                    new_proxies.append(f"http://{m}")
        except Exception as e:
            logger.log(f"抓取 89IP 代理失败：{e}", "WARNING")

        # 去重
        new_proxies = list(set(new_proxies))
        self.proxies = new_proxies
        logger.log(f"获取到 {len(self.proxies)} 个免费代理（已去重）")

    def get_random_proxy(self):
        """随机获取一个代理"""
        if not self.proxies:
            self.fetch_proxies()
        return random.choice(self.proxies) if self.proxies else None

    def validate_proxies(self, max_test=50):
        """验证代理可用性"""
        logger.log(f"正在验证代理可用性（最多测试 {max_test} 个）...")

        import requests
        test_count = 0
        valid_count = 0
        for proxy in self.proxies[:max_test]:
            if self._test_proxy(proxy):
                self.valid_proxies.append(proxy)
                valid_count += 1
                logger.log(f"  可用：{proxy}")
            test_count += 1
            # 找到 5 个可用代理就停止
            if valid_count >= 5:
                break

        logger.log(f"验证完成：{len(self.valid_proxies)}/{test_count} 个代理可用")
        return self.valid_proxies

    def _test_proxy(self, proxy):
        """测试单个代理"""
        try:
            import requests
            # 测试访问 e 互动网站
            resp = requests.get("https://sns.sseinfo.com/",
                              proxies={"http": proxy, "https": proxy},
                              headers=self.headers,
                              timeout=8)
            return resp.status_code == 200
        except:
            return False

    def get_valid_proxy(self):
        """获取一个已验证的代理，如果没有则返回随机代理"""
        if self.valid_proxies:
            return random.choice(self.valid_proxies)
        return self.get_random_proxy()

# 默认起始日期
DEFAULT_START_DATE = "2024-01-01"

# 非法文件名字符
ILLEGAL_CHARS = r'[\\/:*?"<>|]'

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 平台配置
PLATFORMS = {
    "hdy": {
        "name": "互动易（深市）",
        "file_prefix": "HDY",
    },
    "ehd": {
        "name": "e 互动（沪市）",
        "file_prefix": "EHD",
    },
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
        log_line = f"[{timestamp}] [IRM] [{level}] {message}"
        print(log_line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")


# 全局日志实例
logger = None


# ============== 数据库操作 ==============
def init_database():
    """初始化 SQLite 数据库"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='irm_history'")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        cursor.execute('''
            CREATE TABLE irm_history (
                ticker TEXT NOT NULL,
                platform TEXT NOT NULL,
                last_question_date TEXT NOT NULL,
                updated_at TEXT,
                PRIMARY KEY (ticker, platform)
            )
        ''')
        conn.commit()
        logger.log("数据库表创建：irm_history")

    conn.close()
    logger.log(f"数据库初始化完成：{DB_PATH}")


def get_last_question_date(ticker, platform):
    """获取某只股票上次抓取的日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_question_date FROM irm_history WHERE ticker = ? AND platform = ?",
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
        "INSERT OR REPLACE INTO irm_history (ticker, platform, last_question_date, updated_at) VALUES (?, ?, ?, ?)",
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


def clean_filename(title):
    """清洗标题中的非法字符"""
    cleaned = re.sub(ILLEGAL_CHARS, "_", title)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned.strip()


# ============== 互动易 API ==============
def fetch_org_ids():
    """获取 orgId 映射表"""
    url = "https://www.cninfo.com.cn/new/data/szse_stock.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {s['code']: s['orgId'] for s in data.get('stockList', [])}
    except Exception as e:
        logger.log(f"获取 orgId 映射表失败：{e}", "ERROR")
        return {}


def fetch_hdy_questions(stock_code, org_id, start_date, proxy=None):
    """
    获取深交所互动易问答记录

    Args:
        stock_code: 6 位股票代码
        org_id: 机构 ID
        start_date: 开始日期 YYYY-MM-DD
        proxy: 代理地址（可选）

    Returns:
        DataFrame: 问答记录
    """
    url = "https://irm.cninfo.com.cn/newircs/company/question"
    params = {
        "_t": "1691142650",
        "stockcode": stock_code,
        "orgId": org_id,
        "pageSize": "1000",
        "pageNum": "1",
        "keyWord": "",
        "startDay": "",
        "endDay": "",
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        resp = requests.post(url, params=params, headers=HEADERS, proxies=proxies, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        rows = data.get("rows", [])

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # 字段重命名
        rename_map = {
            "mainContent": "问题",
            "attachedContent": "回答内容",
            "pubDate": "提问时间",
            "trade": "行业",
            "companyShortName": "公司简称",
            "stockCode": "股票代码",
        }
        df = df.rename(columns=rename_map)

        # 过滤有回答的记录
        if '回答内容' in df.columns:
            df = df[df['回答内容'].notna()]

        # 日期过滤
        if '提问时间' in df.columns and not df.empty:
            df['date'] = pd.to_datetime(df['提问时间'], unit='ms', errors='coerce').dt.strftime('%Y-%m-%d')
            df = df[df['date'] >= start_date]

        return df

    except Exception as e:
        logger.log(f"获取互动易数据失败：{e}", "WARNING")
        return pd.DataFrame()


# ============== e 互动 API ==============
def fetch_ehd_uids(proxy=None):
    """获取 e 互动公司 uid 映射表"""
    url = "https://sns.sseinfo.com/allcompany.do"
    uid_map = {}

    proxies = {"http": proxy, "https": proxy} if proxy else None

    for page in range(1, 73):
        data = {
            "code": "0",
            "order": "2",
            "areaId": "0",
            "page": str(page),
        }
        try:
            resp = requests.post(url, data=data, headers=HEADERS, proxies=proxies, timeout=30)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            tags = soup.find_all('a', attrs={"rel": "tag"})

            if not tags:
                break

            for tag in tags:
                try:
                    code = tag.find("img")["src"].split("?")[0].split("/")[-1].split(".")[0]
                    uid = tag["uid"]
                    uid_map[code] = uid
                except:
                    continue

            logger.log(f"已获取 {page} 页 e 互动公司列表...")
            time.sleep(0.5)

        except Exception as e:
            logger.log(f"获取 e 互动公司列表失败：{e}", "WARNING")
            break

    return uid_map


def fetch_ehd_questions(stock_code, uid, start_date, proxy=None):
    """
    获取上证 e 互动问答记录

    Args:
        stock_code: 6 位股票代码
        uid: 公司 uid
        start_date: 开始日期 YYYY-MM-DD
        proxy: 代理地址（可选）

    Returns:
        DataFrame: 问答记录
    """
    url = "https://sns.sseinfo.com/ajax/userfeeds.do"

    big_df = pd.DataFrame()
    page = 1

    proxies = {"http": proxy, "https": proxy} if proxy else None

    while True:
        params = {
            "typeCode": "company",
            "type": "11",
            "pageSize": "100",
            "uid": uid,
            "page": str(page),
        }

        try:
            resp = requests.post(url, params=params, headers=HEADERS, proxies=proxies, timeout=30)

            if resp.status_code != 200 or len(resp.text) < 300:
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            content_list = [item.get_text().strip() for item in soup.find_all("div", attrs={"class": "m_feed_txt"})]

            if not content_list:
                break

            date_list = [item.get_text().strip().split("\n")[0] for item in soup.find_all("div", attrs={"class": "m_feed_from"})]

            q_list = [content_list[i].split(")")[1] for i in range(0, len(content_list), 2)]
            a_list = [content_list[i] for i in range(1, len(content_list), 2)]
            d_q_list = [date_list[i] for i in range(0, len(date_list), 2)]
            d_a_list = [date_list[i] for i in range(1, len(date_list), 2)]

            temp_df = pd.DataFrame({
                "股票代码": [stock_code] * len(q_list),
                "问题": q_list,
                "回答": a_list,
                "问题时间": d_q_list,
                "回答时间": d_a_list,
            })

            big_df = pd.concat([big_df, temp_df], ignore_index=True)
            page += 1
            time.sleep(0.5)

        except Exception as e:
            logger.log(f"获取 e 互动数据失败：{e}", "WARNING")
            break

    if not big_df.empty:
        if '回答时间' in big_df.columns:
            big_df['date'] = pd.to_datetime(big_df['回答时间']).dt.strftime('%Y-%m-%d')
            big_df = big_df[big_df['date'] >= start_date]

    return big_df


# ============== 文件保存 ==============
def save_qa_file(filepath, question, answer, publish_date, platform, record=None):
    """保存问答记录到文件"""
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
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    except Exception as e:
        logger.log(f"保存文件失败：{e}", "ERROR")
        return False


# ============== 主处理流程 ==============
def process_stock(ticker, company_name, stock_code, exchange, platform, attachment_dir, orgid_map=None, ehd_uid_map=None, proxy=None):
    """处理单只股票"""
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
        # 深市 - 互动易（可直连）
        if not orgid_map:
            logger.log("  orgId 映射表为空，跳过", "WARNING")
            return 0

        org_id = orgid_map.get(stock_code)
        if not org_id:
            logger.log("  未找到 orgId，跳过", "WARNING")
            return 0

        records = fetch_hdy_questions(stock_code, org_id, last_date, proxy=None)  # 互动易直连

    else:
        # 沪市 - e 互动（需要代理）
        if not ehd_uid_map:
            logger.log("  e 互动 uid 映射表为空，跳过", "WARNING")
            return 0

        uid = ehd_uid_map.get(stock_code)
        if not uid:
            logger.log("  未找到 uid，跳过", "WARNING")
            return 0

        records = fetch_ehd_questions(stock_code, uid, last_date, proxy=proxy)

    if records.empty:
        logger.log("  无新数据")
        return 0

    logger.log(f"  发现 {len(records)} 条新问答")

    # 保存问答记录
    latest_date = last_date
    saved_count = 0

    for index, record in records.iterrows():
        question = clean_html_tags(record.get('问题', ''))
        answer = clean_html_tags(record.get('回答内容' if '回答内容' in record else '回答', ''))

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


def process_all_stocks(df, attachment_dir, proxy=None, skip_ehd=False):
    """逐只股票处理下载"""
    stats = {
        "hdy": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
        "ehd": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
    }

    # 加载映射表
    logger.log("正在加载 orgId 映射表...")
    orgid_map = fetch_org_ids()
    logger.log(f"orgId 映射表加载完成，共 {len(orgid_map)} 条记录")

    ehd_uid_map = None
    if not skip_ehd:
        logger.log("正在加载 e 互动 uid 映射表...")
        ehd_uid_map = fetch_ehd_uids()
        logger.log(f"e 互动 uid 映射表加载完成，共 {len(ehd_uid_map)} 条记录")

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
            if exchange == "sz":
                stats["hdy"]["processed"] += 1
                downloaded = process_stock(ticker, company_name, stock_code, exchange, "hdy", attachment_dir,
                                          orgid_map=orgid_map, proxy=proxy)
                if downloaded == 0:
                    stats["hdy"]["no_data"] += 1
                stats["hdy"]["downloaded"] += downloaded

            elif exchange == "sh":
                if skip_ehd:
                    logger.log(f"跳过 {ticker}：用户选择跳过 e 互动", "WARNING")
                    stats["ehd"]["failed"] += 1
                else:
                    stats["ehd"]["processed"] += 1
                    downloaded = process_stock(ticker, company_name, stock_code, exchange, "ehd", attachment_dir,
                                              ehd_uid_map=ehd_uid_map, proxy=proxy)
                    if downloaded == 0:
                        stats["ehd"]["no_data"] += 1
                    stats["ehd"]["downloaded"] += downloaded

            else:
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


def process_all_stocks_with_proxy_pool(df, attachment_dir, proxy_pool):
    """使用代理池逐只股票处理下载 - 实际上 e 互动可直接访问"""
    stats = {
        "hdy": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
        "ehd": {"downloaded": 0, "processed": 0, "no_data": 0, "failed": 0},
    }

    # 加载映射表
    logger.log("正在加载 orgId 映射表...")
    orgid_map = fetch_org_ids()
    logger.log(f"orgId 映射表加载完成，共 {len(orgid_map)} 条记录")

    # e 互动 uid 映射表 - 直接访问，不需要代理
    logger.log("正在加载 e 互动 uid 映射表（直连模式）...")
    ehd_uid_map = fetch_ehd_uids(proxy=None)  # 直连
    logger.log(f"e 互动 uid 映射表加载完成，共 {len(ehd_uid_map)} 条记录")

    total = len(df)
    retry_count = 0
    max_retries = 3

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
            if exchange == "sz":
                stats["hdy"]["processed"] += 1
                downloaded = process_stock(ticker, company_name, stock_code, exchange, "hdy", attachment_dir,
                                          orgid_map=orgid_map, proxy=None)  # 深市直连
                if downloaded == 0:
                    stats["hdy"]["no_data"] += 1
                stats["hdy"]["downloaded"] += downloaded

            elif exchange == "sh":
                stats["ehd"]["processed"] += 1
                # 直连 e 互动，不需要代理
                downloaded = process_stock(ticker, company_name, stock_code, exchange, "ehd", attachment_dir,
                                          ehd_uid_map=ehd_uid_map, proxy=None)
                if downloaded == 0:
                    stats["ehd"]["no_data"] += 1
                stats["ehd"]["downloaded"] += downloaded
                retry_count = 0  # 成功后重置重试计数

            else:
                logger.log(f"跳过 {ticker}：不支持的交易所 {exchange}", "WARNING")

        except Exception as e:
            logger.log(f"[{ticker}] 处理失败：{e}", "ERROR")
            retry_count += 1
            if retry_count >= max_retries:
                logger.log(f"连续失败 {max_retries} 次，重新获取代理...", "WARNING")
                proxy_pool.fetch_proxies()
                retry_count = 0
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


def main():
    """主函数"""
    global logger

    print("=" * 60)
    print("投资者关系活动记录表下载器（原生 requests + 免费代理池）")
    print("支持：深交所互动易 + 上证 e 互动")
    print("=" * 60)

    # 初始化日志
    logger = Logger(LOG_PATH)
    logger.log("程序启动")

    # 初始化数据库
    init_database()
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    # 代理配置
    proxy = None
    use_proxy_pool = False

    print("\n代理配置:")
    print("1. 互动易（深市）可直接访问，无需代理")
    print("2. e 互动（沪市）使用免费代理池")
    print()

    # 自动使用免费代理池
    logger.log("使用免费代理池...")
    proxy_pool = SimpleProxyPool()
    proxy_pool.fetch_proxies()
    # 自动验证前 10 个代理
    proxy_pool.validate_proxies(max_test=10)
    use_proxy_pool = True
    logger.log(f"免费代理池初始化完成，{len(proxy_pool.valid_proxies)} 个可用代理")

    # 加载公司列表
    df = load_company_list()

    # 统计各交易所数量
    exchange_counts = df['exchange'].value_counts()
    logger.log(f"交易所分布：{dict(exchange_counts)}")

    # 逐只股票处理
    if use_proxy_pool:
        stats = process_all_stocks_with_proxy_pool(df, ATTACHMENT_DIR, proxy_pool=proxy_pool)
    else:
        stats = process_all_stocks(df, ATTACHMENT_DIR, proxy=proxy, skip_ehd=False)

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
