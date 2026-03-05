#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
港交所新闻爬虫 - Playwright 版
使用 Playwright 获取动态加载的新闻数据
"""

import os
import sys
import sqlite3
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class HKEXNewsCrawler(BaseCrawler):
    """港交所新闻爬虫"""

    def __init__(self):
        super().__init__(name="HKEXNews")
        self.url = 'https://www.hkex.com.hk/News/News-Release?sc_lang=zh-HK&Year=ALL&NewsCategory=&currentCount=2000'

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS exchange_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                security_code TEXT,
                security_name TEXT,
                title TEXT NOT NULL,
                pub_date TEXT NOT NULL,
                category TEXT,
                link TEXT UNIQUE NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_announcements_exchange ON exchange_announcements(exchange)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_announcements_pub_date ON exchange_announcements(pub_date)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def fetch_news(self) -> List[Dict]:
        """使用 Playwright 获取新闻列表"""
        try:
            from playwright.sync_api import sync_playwright

            items = []

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.url, timeout=30000)
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(3000)

                # 获取完整 HTML
                html = page.content()
                browser.close()

                # 解析 HTML
                from lxml import html as lh
                doc = lh.fromstring(html.encode('utf-8'))

                # 查找新闻链接（排除 PDF 链接）
                links = doc.xpath('//a[contains(@href, "/News/News-Release/") and not(contains(@href, ".pdf"))]')

                seen_urls = set()
                for link in links:
                    href = link.get('href', '')
                    title = link.text_content().strip()

                    if not title or href in seen_urls:
                        continue

                    seen_urls.add(href)

                    # 提取日期（从 URL 中提取年份）
                    pub_date = self._extract_date_from_url(href)

                    # 提取类别
                    category = self._extract_category(title)

                    items.append({
                        'PubDate': pub_date,
                        'NewsTag': category,
                        'NewsUrl': 'https://www.hkex.com.hk' + href,
                        'NewsTitle': title
                    })

            return items

        except ImportError:
            self.logger.log("Playwright 未安装，使用简化模式", "WARNING")
            return self._fetch_simple()
        except Exception as e:
            self.logger.log(f"获取页面失败：{e}", "ERROR")
            return self._fetch_simple()

    def _extract_date_from_url(self, url: str) -> str:
        """从 URL 提取日期"""
        import re
        # URL 格式：/News/News-Release/2026/260227news?sc_lang=zh-HK
        match = re.search(r'/(\d{2})(\d{2})(\d{2})news', url)
        if match:
            year = '20' + match.group(1)
            month = match.group(2)
            day = match.group(3)
            return f"{year}-{month}-{day}"
        return datetime.now().strftime('%Y-%m-%d')

    def _extract_category(self, title: str) -> str:
        """从标题提取类别"""
        keywords = {
            '業績': '业绩公告',
            '業績報告': '业绩公告',
            '董事會': '董事会会议',
            '董事會會議': '董事会会议',
            '委任': '人事变动',
            '任命': '人事变动',
            '辭任': '人事变动',
            '公告': '一般公告',
            '文件': '文件披露',
        }
        for keyword, category in keywords.items():
            if keyword in title:
                return category
        return '其他'

    def _fetch_simple(self) -> List[Dict]:
        """简化版获取（备用方案）"""
        import requests
        from lxml import html

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
        }

        try:
            resp = requests.get(self.url, headers=headers, timeout=15)
            resp.raise_for_status()
            page = resp.text

            doc = html.fromstring(page)
            links = doc.xpath('//a[contains(@href, "/News/News-Release/") and not(contains(@href, ".pdf"))]')

            items = []
            for link in links[:20]:
                href = link.get('href', '')
                title = link.text_content().strip()
                if title:
                    items.append({
                        'PubDate': self._extract_date_from_url(href),
                        'NewsTag': self._extract_category(title),
                        'NewsUrl': 'https://www.hkex.com.hk' + href,
                        'NewsTitle': title
                    })

            return items
        except:
            return []

    def save_announcements(self, items: List[Dict]) -> int:
        """保存公告到数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = 0
        for item in items:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO exchange_announcements
                    (exchange, title, pub_date, category, link)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'HKEX',
                    item['NewsTitle'],
                    item['PubDate'],
                    item['NewsTag'],
                    item['NewsUrl']
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                self.logger.log(f"插入失败：{e}", "DEBUG")

        conn.commit()
        conn.close()
        return inserted

    def crawl(self) -> int:
        """
        爬取港交所新闻

        Returns:
            新增公告数量
        """
        self.init_db()

        self.logger.log("开始爬取港交所新闻...")
        items = self.fetch_news()

        if not items:
            self.logger.log("未获取到数据", "WARNING")
            return 0

        inserted = self.save_announcements(items)

        self.logger.log(f"爬取完成，获取{len(items)}条，新增{inserted}条")
        return inserted


def main():
    """独立运行"""
    crawler = HKEXNewsCrawler()
    crawler.crawl()

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM exchange_announcements WHERE exchange="HKEX"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT category, COUNT(*), MAX(pub_date)
        FROM exchange_announcements
        WHERE exchange = 'HKEX'
        GROUP BY category
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("港交所新闻爬取结果")
    print("=" * 50)
    print(f"港交所公告总数：{total} 条")
    print("\n按类别统计:")
    for stat in stats:
        print(f"  {stat[0] or '未分类'}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
