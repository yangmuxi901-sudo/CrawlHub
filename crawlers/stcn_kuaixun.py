#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
证券时报爬虫 - 简化版
基于 JustSimpleSpider/StockStcn/kuaixun.py 改造
"""

import os
import sys
import json
import time
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict
from lxml import html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class STCNKuaixunCrawler(BaseCrawler):
    """证券时报 - 快讯"""

    def __init__(self):
        super().__init__(name="STCNKuaixun")
        self.base_url = "https://kuaixun.stcn.com/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.stcn.com/",
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
                    source TEXT DEFAULT '证券时报',
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

    def fetch_news_list(self, page: int = 1) -> List[Dict]:
        """获取快讯列表"""
        if page == 1:
            url = "https://kuaixun.stcn.com/index.html"
        else:
            url = f"https://kuaixun.stcn.com/index_{page}.html"

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            page_content = resp.text

            doc = html.fromstring(page_content)
            items = []

            # 尝试不同的 XPath 选择器
            columns = doc.xpath("//ul[@id='news_list2']/li")
            if not columns:
                columns = doc.xpath("//div[@class='list-main']//li")

            for column in columns[:20]:
                try:
                    title_elements = column.xpath("./a[@title]")
                    if not title_elements:
                        title_elements = column.xpath(".//a[contains(@href, '.html')]")
                    if not title_elements:
                        continue

                    title = title_elements[0].get("title", "")
                    if not title:
                        title = title_elements[0].text_content().strip()[:60]

                    link = title_elements[0].get("href", "")
                    if link and link.startswith("./"):
                        link = "https://kuaixun.stcn.com" + link[1:]
                    elif link and not link.startswith("http"):
                        link = "https://kuaixun.stcn.com" + link

                    # 提取时间
                    time_elem = column.xpath("./span")
                    pub_date = ""
                    if time_elem:
                        pub_date = time_elem[0].text_content().strip()[:16]

                    if title and link:
                        items.append({
                            "title": title[:120],
                            "source": "证券时报",
                            "pub_date": pub_date,
                            "link": link,
                            "article": "",
                            "category": "快讯",
                        })
                except Exception as e:
                    self.logger.log(f"解析新闻失败：{e}", "DEBUG")
                    continue

            return items

        except Exception as e:
            self.logger.log(f"获取快讯列表失败：{e}", "ERROR")
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
        爬取快讯

        Args:
            pages: 爬取页数

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        self.logger.log(f"开始爬取证券时报快讯，计划爬取{pages}页...")

        for page in range(1, pages + 1):
            self.logger.log(f"正在爬取第{page}页...")
            news_list = self.fetch_news_list(page)

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
    crawler = STCNKuaixunCrawler()
    crawler.crawl(pages=3)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="证券时报"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("证券时报爬取结果")
    print("=" * 50)
    print(f"证券时报总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
