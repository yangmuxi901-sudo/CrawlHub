#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
搜狐财经爬虫 - 简化版
无需 MySQL 配置，直接使用 SQLite

注意：搜狐财经 API 有反爬限制，改用网页版爬取
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime
from typing import List, Dict
import requests
from lxml import html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class SohuFinanceCrawler(BaseCrawler):
    """搜狐财经爬虫"""

    def __init__(self):
        super().__init__(name="SohuFinance")
        # 使用网页版
        self.list_url = 'https://m.sohu.com/ch/15'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def init_db(self):
        """初始化新闻表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT DEFAULT '搜狐财经',
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

    def fetch_news_list(self, page: int = 1) -> List[Dict]:
        """
        获取新闻列表
        从网页版提取新闻
        """
        try:
            # 网页版 URL
            url = f'{self.list_url}?page={page}'
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            doc = html.fromstring(resp.text)

            items = []

            # 查找新闻链接
            links = doc.xpath('//a[@href and contains(@href, "/a/")]')

            for link in links:
                href = link.get('href', '')
                title = link.text_content().strip()

                if not title or len(title) < 5:
                    continue

                # 提取时间（如果有）
                time_elem = link.xpath('.//span[contains(@class, "time")]')
                if time_elem:
                    pub_date = time_elem[0].text_content().strip()
                else:
                    pub_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                items.append({
                    'title': title[:100],
                    'source': '搜狐财经',
                    'pub_date': pub_date,
                    'link': f'https://m.sohu.com{href}',
                })

            return items

        except Exception as e:
            self.logger.log(f"获取新闻列表失败：{e}", "ERROR")
            return []

    def fetch_article(self, url: str) -> str:
        """获取新闻正文"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            from lxml import html
            doc = html.fromstring(resp.text)

            # 搜狐财经文章正文选择器
            selectors = [
                "//section[@id='articleContent']",
                "//article[@class='article']",
                "//div[@class='article-content']",
            ]

            for selector in selectors:
                elements = doc.xpath(selector)
                if elements:
                    content = elements[0].text_content().strip()
                    # 清理空白字符
                    content = ' '.join(content.split())
                    return content[:10000]

            return ""

        except Exception as e:
            self.logger.log(f"获取正文失败：{url} - {e}", "DEBUG")
            return ""

    def save_news(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
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
                    news.get('article', '')
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                self.logger.log(f"插入失败：{e}", "DEBUG")

        conn.commit()
        conn.close()
        return inserted

    def crawl(self, pages: int = 3, fetch_articles: bool = False) -> int:
        """
        爬取新闻

        Args:
            pages: 爬取页数
            fetch_articles: 是否获取正文（耗时较长）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0

        self.logger.log(f"开始爬取搜狐财经新闻，计划爬取{pages}页...")

        for page in range(1, pages + 1):
            news_list = self.fetch_news_list(page)

            if not news_list:
                self.logger.log(f"第{page}页无数据，停止爬取", "INFO")
                break

            # 如果需要获取正文
            if fetch_articles:
                for news in news_list:
                    article = self.fetch_article(news['link'])
                    news['article'] = article

            inserted = self.save_news(news_list)
            total_inserted += inserted

            self.logger.log(f"第{page}页：获取{len(news_list)}条，新增{inserted}条")

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = SohuFinanceCrawler()
    crawler.crawl(pages=3, fetch_articles=False)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="搜狐财经"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("搜狐财经爬取结果")
    print("=" * 50)
    print(f"新闻总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
