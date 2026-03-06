#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
东方财富网新闻爬虫
爬取东方财富财经新闻、个股公告等
"""

import os
import sys
import json
import time
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class EastMoneyNewsCrawler(BaseCrawler):
    """东方财富网新闻爬虫"""

    def __init__(self):
        super().__init__(name="EastMoney")
        # 东方财富 API 端点
        self.api_url = "https://api.eastmoney.com/news/api/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.eastmoney.com/",
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
                    source TEXT DEFAULT '东方财富',
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

    def fetch_news(self, page: int = 1, page_size: int = 20) -> List[Dict]:
        """获取新闻列表"""
        try:
            # 东方财富要闻 API
            url = "https://api.eastmoney.com/news/api/getlastestnews"
            params = {
                "pn": str(page),
                "ps": str(page_size),
                "rt": str(int(time.time() * 1000)),
            }

            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data or not data.get("data"):
                return []

            news_list = []
            for item in data.get("data", []):
                title = item.get("Title", "")
                content = item.get("Content", "")
                pub_time = item.get("PublicTime", "")
                news_id = item.get("Id", "")
                news_type = item.get("Type", "")

                if title:
                    news_list.append({
                        "title": title[:120],
                        "source": "东方财富",
                        "pub_date": pub_time[:19] if pub_time else "",
                        "link": f"https://www.eastmoney.com/a/{news_id}.html",
                        "article": content[:1000] if content else "",
                        "category": self._get_category(news_type),
                    })

            return news_list

        except Exception as e:
            self.logger.log(f"获取新闻失败：{e}", "ERROR")
            return []

    def _get_category(self, news_type: str) -> str:
        """根据新闻类型获取分类"""
        category_map = {
            "1": "要闻",
            "2": "宏观",
            "3": "策略",
            "4": "市场",
            "5": "热点",
            "6": "个股",
            "7": "研报",
        }
        return category_map.get(news_type, "其他")

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
        爬取东方财富新闻

        Args:
            pages: 爬取页数

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        self.logger.log(f"开始爬取东方财富新闻，计划爬取{pages}页...")

        for page in range(1, pages + 1):
            self.logger.log(f"正在爬取第{page}页...")
            news_list = self.fetch_news(page)

            if not news_list:
                self.logger.log(f"第{page}页无数据，停止爬取", "INFO")
                break

            inserted = self.save_news(news_list)
            total_inserted += inserted
            self.logger.log(f"第{page}页：获取{len(news_list)}条，新增{inserted}条")

            if inserted == 0 and page > 1:
                self.logger.log("无新数据，停止爬取", "INFO")
                break

            time.sleep(1)

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = EastMoneyNewsCrawler()
    crawler.crawl(pages=3)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="东方财富"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("东方财富爬取结果")
    print("=" * 50)
    print(f"东方财富总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
