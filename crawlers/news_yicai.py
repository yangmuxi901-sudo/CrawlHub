#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一财经新闻爬虫 - 简化版
无需 MySQL 配置，直接使用 SQLite
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger
import requests
from lxml import html


class YiCaiNewsCrawler(BaseCrawler):
    """第一财经新闻爬虫"""

    def __init__(self):
        super().__init__(name="YiCaiNews")
        self.index_url = 'https://www.yicai.com/'
        self.api_url = 'https://www.yicai.com/api/ajax/getlatest'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.yicai.com/',
        }

    def init_db(self):
        """初始化新闻表"""
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT DEFAULT '第一财经',
                pub_date TEXT,
                link TEXT,
                article TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(link)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def fetch_news(self, page: int = 1) -> List[Dict]:
        """获取新闻列表"""
        params = {
            'page': page,
            'pagesize': 25
        }

        try:
            resp = requests.get(self.api_url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return []

            news_list = []
            for item in data:
                url = item.get("url", "")
                # 跳过视频内容
                if "video" in url:
                    continue

                title = item.get("NewsTitle", "")
                source = item.get("NewsSource", "")
                author = item.get("NewsAuthor", "")
                last_date = item.get("LastDate", "")

                # 解析时间
                try:
                    pub_date = datetime.strptime(last_date, "%Y-%m-%dT%H:%M:%S")
                    pub_date_str = pub_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pub_date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                link = "https://www.yicai.com" + url

                # 获取正文
                article = self.fetch_detail_page(link)

                news_list.append({
                    'title': title[:100],
                    'source': source or '第一财经',
                    'author': author,
                    'pub_date': pub_date_str,
                    'link': link,
                    'article': article or ''
                })

            return news_list

        except Exception as e:
            self.logger.log(f"获取新闻失败：{e}", "ERROR")
            return []

    def fetch_detail_page(self, url: str) -> str:
        """获取新闻正文"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            doc = html.fromstring(resp.text)
            # 尝试不同的正文选择器
            selectors = [
                ".//div[@class='m-txt']",
                ".//div[@class='article-content']",
                ".//article",
            ]

            for selector in selectors:
                elements = doc.xpath(selector)
                if elements:
                    return elements[0].text_content().strip()

            return ""

        except Exception as e:
            self.logger.log(f"获取正文失败：{url} - {e}", "DEBUG")
            return ""

    def save_news(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = 0
        for news in news_list:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO finance_news
                    (title, source, pub_date, link, article)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    news['title'],
                    news['source'],
                    news['pub_date'],
                    news['link'],
                    news['article']
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
        爬取新闻

        Args:
            pages: 爬取页数（每页 25 条）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0

        self.logger.log(f"开始爬取第一财经新闻，计划爬取{pages}页...")

        for page in range(1, pages + 1):
            news_list = self.fetch_news(page)

            if not news_list:
                self.logger.log(f"第{page}页无数据，停止爬取", "INFO")
                break

            inserted = self.save_news(news_list)
            total_inserted += inserted

            self.logger.log(f"第{page}页：获取{len(news_list)}条，新增{inserted}条")

            time.sleep(1)  # 避免请求过快

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = YiCaiNewsCrawler()
    crawler.crawl(pages=3)

    # 显示统计
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("第一财经新闻爬取结果")
    print("=" * 50)
    print(f"新闻总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
