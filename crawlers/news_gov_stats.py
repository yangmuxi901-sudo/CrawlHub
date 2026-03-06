#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国家统计局爬虫 - 简化版
无需 MySQL 配置，直接使用 SQLite
"""

import os
import sys
import sqlite3
from datetime import datetime
from typing import List, Dict
import requests
from lxml import html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class GovStatsCrawler(BaseCrawler):
    """国家统计局爬虫"""

    def __init__(self):
        super().__init__(name="GovStats")
        self.base_url = 'http://www.stats.gov.cn'
        self.list_url = 'http://www.stats.gov.cn/sj/zxfb/index.html'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def init_db(self):
        """初始化新闻表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT DEFAULT '国家统计局',
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
        """获取新闻列表"""
        if page == 1:
            url = self.list_url
        else:
            url = f'http://www.stats.gov.cn/sj/zxfb/index_{page}.html'

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            doc = html.fromstring(resp.text)

            items = []
            import re

            # 查找所有链接
            all_links = doc.xpath('//a[@href]')

            for link in all_links:
                href = link.get('href', '')

                # 匹配新闻链接格式：./YYYYMM/tYYYYMMDD_XXXXXXX.html
                if not (href.startswith('./') and '/t' in href and '.html' in href):
                    continue

                # 跳过非新闻链接
                if any(x in href for x in ['wzgl/', 'xglj/']):
                    continue

                title = link.text_content().strip()
                if len(title) < 5:
                    continue

                # 从 URL 中提取日期
                date_match = re.search(r't(\d{8})_', href)
                if date_match:
                    date_str = date_match.group(1)
                    pub_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    pub_date = datetime.now().strftime('%Y-%m-%d')

                # 处理相对 URL
                if href.startswith('./'):
                    # 替换 ./ 为当前目录 URL
                    base = self.list_url.rsplit('/', 1)[0]
                    href = f'{base}/{href[2:]}'

                items.append({
                    'title': title[:100],
                    'source': '国家统计局',
                    'pub_date': pub_date,
                    'link': href,
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

            doc = html.fromstring(resp.text)

            # 尝试不同的正文选择器
            selectors = [
                "//div[@class='TRS_PreAppend']",
                "//div[@class='TRS_Editor']",
                "//div[@class='center_xilan']",
                "//div[@id='content']",
            ]

            for selector in selectors:
                elements = doc.xpath(selector)
                if elements:
                    content = elements[0].text_content().strip()
                    # 清理空白字符
                    content = ' '.join(content.split())
                    return content[:10000]  # 限制长度

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

        self.logger.log(f"开始爬取国家统计局新闻，计划爬取{pages}页...")

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
    crawler = GovStatsCrawler()
    crawler.crawl(pages=3, fetch_articles=False)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="国家统计局"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("国家统计局爬取结果")
    print("=" * 50)
    print(f"新闻总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
