#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
巨潮资讯网爬虫 - Playwright版
数据源：http://www.cninfo.com.cn/
爬取 A 股上市公司最新公告
"""

import os
import sys
import sqlite3
import warnings
import time
from datetime import datetime
from typing import List, Dict

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class CNInfoAnnouncementCrawler(BaseCrawler):
    """巨潮资讯网公告爬虫 - Playwright版"""

    def __init__(self):
        super().__init__(name="CNInfo")
        # 巨潮资讯公告页面（深交所）
        self.url = "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice#szse"

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

    def fetch_announcements(self) -> List[Dict]:
        """使用 Playwright 获取公告"""
        try:
            from playwright.sync_api import sync_playwright

            announcements = []

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                self.logger.log(f"正在加载页面: {self.url}")
                page.goto(self.url, timeout=30000)
                page.wait_for_load_state('networkidle')
                time.sleep(3)  # 等待动态内容加载

                # 获取表格中的行
                rows = page.query_selector_all('table tbody tr')
                self.logger.log(f"找到 {len(rows)} 条公告")

                for row in rows:
                    try:
                        cells = row.query_selector_all('td')
                        if len(cells) < 3:
                            continue

                        # 解析单元格
                        code = cells[0].inner_text().strip() if cells[0] else ""
                        name = cells[1].inner_text().strip() if cells[1] else ""

                        # 标题和链接
                        title_cell = cells[2]
                        title = title_cell.inner_text().strip() if title_cell else ""
                        link_el = title_cell.query_selector('a') if title_cell else None
                        link = link_el.get_attribute('href') if link_el else ""

                        # 日期
                        pub_date = ""
                        if len(cells) > 3 and cells[3]:
                            pub_date = cells[3].inner_text().strip()

                        if not title or not link:
                            continue

                        # 构建完整链接
                        if link and not link.startswith('http'):
                            link = 'http://www.cninfo.com.cn' + link

                        # 标准化时间格式
                        if pub_date:
                            try:
                                # 尝试解析日期格式
                                pub_date = pub_date.replace('\n', ' ').strip()[:19]
                            except Exception:
                                pub_date = datetime.now().strftime("%Y-%m-%d")
                        else:
                            pub_date = datetime.now().strftime("%Y-%m-%d")

                        announcements.append({
                            "exchange": "CNINFO",
                            "security_code": code,
                            "security_name": name,
                            "title": title[:200],
                            "pub_date": pub_date,
                            "category": "公告",
                            "link": link,
                            "content": "",
                        })

                    except Exception as e:
                        self.logger.log(f"解析行失败：{e}", "DEBUG")
                        continue

                browser.close()

            return announcements

        except Exception as e:
            self.logger.log(f"获取公告失败：{e}", "ERROR")
            return []

    def save_announcements(self, announcements: List[Dict]) -> int:
        """保存公告到数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = 0
        for item in announcements:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO exchange_announcements
                    (exchange, security_code, security_name, title, pub_date, category, link, content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item["exchange"],
                    item["security_code"],
                    item["security_name"],
                    item["title"],
                    item["pub_date"],
                    item["category"],
                    item["link"],
                    item["content"],
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
        爬取巨潮资讯公告

        Returns:
            新增公告数量
        """
        self.init_db()

        self.logger.log("开始爬取巨潮资讯网公告...")

        announcements = self.fetch_announcements()

        if not announcements:
            self.logger.log("无公告数据", "WARNING")
            return 0

        inserted = self.save_announcements(announcements)
        self.logger.log(f"获取{len(announcements)}条，新增{inserted}条")
        self.logger.log(f"爬取完成，共新增{inserted}条公告", "SUCCESS")
        return inserted


def main():
    """独立运行"""
    crawler = CNInfoAnnouncementCrawler()
    crawler.crawl()

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM exchange_announcements WHERE exchange="CNINFO"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT security_code, security_name, title, pub_date
        FROM exchange_announcements
        WHERE exchange = 'CNINFO'
        ORDER BY id DESC
        LIMIT 5
    ''')
    recent = cursor.fetchall()

    print("\n" + "=" * 60)
    print("巨潮资讯爬取结果")
    print("=" * 60)
    print(f"巨潮公告总数：{total} 条")
    print("\n最近5条公告:")
    for r in recent:
        print(f"  {r[0]} {r[1]}: {r[2][:30]}... ({r[3]})")

    conn.close()


if __name__ == "__main__":
    main()
