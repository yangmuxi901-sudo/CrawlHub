#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中国人民银行爬虫 - 简化版
无需 MySQL 配置，直接使用 SQLite
"""

import os
import sys
import re
import sqlite3
from datetime import datetime
from typing import List, Dict
import requests
from lxml import html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class PBOCCrawler(BaseCrawler):
    """中国人民银行爬虫"""

    def __init__(self):
        super().__init__(name="PBOC")
        self.base_url = 'http://www.pbc.gov.cn'
        # 新闻发布栏目
        self.list_url = 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html'
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
                source TEXT DEFAULT '中国人民银行',
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

    def fetch_news_list(self) -> List[Dict]:
        """
        获取新闻列表
        中国人民银行网站结构特殊，需要从主页提取所有新闻链接
        """
        try:
            resp = requests.get(self.list_url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            doc = html.fromstring(resp.text)

            items = []

            # 查找所有新闻链接（格式：/goutongjiaoliu/113456/113469/YYYYMMDD.../index.html）
            links = doc.xpath('//a[contains(@href, "/goutongjiaoliu/113456/113469/")]')

            for link in links:
                href = link.get('href', '')

                # 跳过主页链接
                if href.endswith('/index.html') and '113469/index.html' in href:
                    continue

                # 提取标题
                title = link.text_content().strip()
                if not title or len(title) < 5:
                    continue

                # 从 URL 中提取日期（格式：20260303...）
                date_match = re.search(r'/(\d{8})', href)
                if date_match:
                    date_str = date_match.group(1)
                    pub_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    pub_date = datetime.now().strftime('%Y-%m-%d')

                # 处理相对 URL
                if href.startswith('/'):
                    href = self.base_url + href

                items.append({
                    'title': title[:100],
                    'source': '中国人民银行',
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

            # 中国人民银行使用<div id="zoom">包含正文
            zoom_elem = doc.xpath('//div[@id="zoom"]')
            if zoom_elem:
                # 提取文本，排除表格内容
                content_parts = []
                for child in zoom_elem[0]:
                    if child.tag != 'table':
                        text = child.text_content().strip()
                        if text:
                            content_parts.append(text)

                content = '\n'.join(content_parts)
                # 清理空白字符
                content = ' '.join(content.split())
                return content[:10000]

            # 备选方案
            selectors = [
                "//div[@class='TRS_PreAppend']",
                "//div[@class='TRS_Editor']",
                "//div[@class='content']",
            ]

            for selector in selectors:
                elements = doc.xpath(selector)
                if elements:
                    content = elements[0].text_content().strip()
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

    def crawl(self, fetch_articles: bool = False) -> int:
        """
        爬取新闻

        Args:
            fetch_articles: 是否获取正文（耗时较长）

        Returns:
            新增新闻数量
        """
        self.init_db()

        self.logger.log("开始爬取中国人民银行新闻...")

        news_list = self.fetch_news_list()

        if not news_list:
            self.logger.log("无数据", "WARNING")
            return 0

        # 如果需要获取正文
        if fetch_articles:
            self.logger.log(f"获取{len(news_list)}条新闻正文...")
            for i, news in enumerate(news_list):
                article = self.fetch_article(news['link'])
                news['article'] = article
                if (i + 1) % 10 == 0:
                    self.logger.log(f"  已获取 {i + 1}/{len(news_list)} 条")

        inserted = self.save_news(news_list)

        self.logger.log(f"爬取完成，获取{len(news_list)}条，新增{inserted}条新闻", "SUCCESS")
        return inserted


def main():
    """独立运行"""
    crawler = PBOCCrawler()
    crawler.crawl(fetch_articles=False)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="中国人民银行"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("中国人民银行爬取结果")
    print("=" * 50)
    print(f"新闻总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
