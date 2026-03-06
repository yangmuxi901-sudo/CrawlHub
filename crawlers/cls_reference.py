#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
财联社深度专题爬虫
支持栏目：早报、收评、热点板块等
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class CLSReferenceCrawler(BaseCrawler):
    """财联社深度专题爬虫"""

    def __init__(self):
        super().__init__(name="CLSReference")
        self.api_url = "https://www.cls.cn/nodeapi/telegraphList"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.cls.cn/",
        }
        self.params = {
            "app": "CailianpressWeb",
            "category": "",
            "lastTime": "",
            "last_time": "",
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "7.2.2",
            "sign": "",
        }

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='finance_news'")
        if not cursor.fetchone():
            conn.execute('''
                CREATE TABLE IF NOT EXISTS finance_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    source TEXT DEFAULT '财联社深度',
                    pub_date TEXT,
                    link TEXT UNIQUE,
                    article TEXT,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute("PRAGMA table_info(finance_news)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'category' not in columns:
                conn.execute('ALTER TABLE finance_news ADD COLUMN category TEXT')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_category ON finance_news(category)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def generate_sign(self, timestamp: int) -> str:
        """生成请求签名"""
        sign_str = f"CailianpressWeb{timestamp}"
        return hashlib.md5(sign_str.encode()).hexdigest()

    def fetch_news(self, last_time: int = None) -> List[Dict]:
        """获取新闻列表"""
        if last_time is None:
            last_time = int(time.time())

        self.params["lastTime"] = str(last_time)
        self.params["last_time"] = str(last_time)
        self.params["sign"] = self.generate_sign(last_time)

        try:
            resp = requests.get(self.api_url, params=self.params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            roll_data = None
            if data.get("data") and isinstance(data.get("data"), dict):
                roll_data = data.get("data", {}).get("roll_data", [])
            elif data.get("data") and isinstance(data.get("data"), list):
                roll_data = data.get("data", [])

            if not roll_data:
                return self._fetch_homepage()

            news_list = []
            for item in roll_data:
                title = item.get("title", "") or item.get("content", "")[:30]
                content = item.get("content", "")
                pub_time = item.get("ctime", int(time.time()))
                aid = item.get("id", "")

                # 根据内容类型分类
                category = "电报"
                if "早报" in title or " Morning" in content:
                    category = "早报"
                elif "收评" in title or "收盘" in title:
                    category = "收评"

                news_list.append({
                    "title": title[:60],
                    "source": "财联社深度",
                    "pub_date": datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "link": f"https://www.cls.cn/detail/{aid}",
                    "article": content,
                    "category": category,
                })

            return news_list

        except Exception as e:
            self.logger.log(f"获取新闻失败：{e}", "ERROR")
            return self._fetch_homepage()

    def _fetch_homepage(self) -> List[Dict]:
        """备用方案：从首页获取新闻"""
        try:
            mobile_url = "https://www.cls.cn/api/node/roll"
            params = {
                "app": "CailianpressWeb",
                "client": "web",
                "os": "web",
                "sv": "7.2.2",
                "rn": "20",
            }
            resp = requests.get(mobile_url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 200 and data.get("data"):
                roll_data = data.get("data", {}).get("roll_data", []) or data.get("data", [])

                news_list = []
                for item in roll_data[:20]:
                    title = item.get("title", "") or item.get("content", "")[:30]
                    content = item.get("content", "")
                    pub_time = item.get("ctime", int(time.time()))
                    aid = item.get("id", "")

                    category = "电报"
                    if "早报" in title:
                        category = "早报"
                    elif "收评" in title:
                        category = "收评"

                    news_list.append({
                        "title": title[:60],
                        "source": "财联社深度",
                        "pub_date": datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "link": f"https://www.cls.cn/detail/{aid}",
                        "article": content,
                        "category": category,
                    })

                return news_list

            return []

        except Exception as e:
            self.logger.log(f"首页新闻获取失败：{e}", "ERROR")
            return []

    def save_news(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = 0
        for news in news_list:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO finance_news
                    (title, source, pub_date, link, article, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    news["title"],
                    news["source"],
                    news["pub_date"],
                    news["link"],
                    news["article"],
                    news["category"],
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                self.logger.log(f"插入失败：{e}", "DEBUG")

        conn.commit()
        conn.close()
        return inserted

    def crawl(self, pages: int = 3) -> int:
        """
        爬取财联社深度专题

        Args:
            pages: 爬取页数（每页 20 条）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        last_time = int(time.time())

        self.logger.log(f"开始爬取财联社深度专题，计划爬取{pages}页...")

        for page in range(pages):
            news_list = self.fetch_news(last_time)

            if not news_list:
                self.logger.log(f"第{page + 1}页无数据，停止爬取", "INFO")
                break

            inserted = self.save_news(news_list)
            total_inserted += inserted

            self.logger.log(f"第{page + 1}页：获取{len(news_list)}条，新增{inserted}条")

            if inserted == 0:
                self.logger.log("无新数据，停止爬取", "INFO")
                break

            # 更新 last_time 用于下一页
            if news_list:
                try:
                    last_pub_date = news_list[-1]["pub_date"]
                    last_time = int(datetime.strptime(last_pub_date, "%Y-%m-%d %H:%M:%S").timestamp())
                except:
                    pass

            time.sleep(1)

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = CLSReferenceCrawler()
    crawler.crawl()

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="财联社深度"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT category, COUNT(*), MAX(pub_date)
        FROM finance_news
        WHERE source = '财联社深度'
        GROUP BY category
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("财联社深度爬取结果")
    print("=" * 50)
    print(f"财联社深度总数：{total} 条")
    print("\n按栏目统计:")
    for stat in stats:
        print(f"  {stat[0] or '未分类'}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
