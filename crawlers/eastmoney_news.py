#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
东方财富网新闻爬虫 - 基于 AKShare
数据源：AKShare stock_news_em 接口
"""

import os
import sys
import sqlite3
import warnings
from datetime import datetime
from typing import List, Dict

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class EastMoneyNewsCrawler(BaseCrawler):
    """东方财富网新闻爬虫 - AKShare版"""

    def __init__(self):
        super().__init__(name="EastMoney")

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT,
                pub_date TEXT,
                link TEXT UNIQUE,
                article TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def fetch_news(self) -> List[Dict]:
        """使用 AKShare 获取新闻"""
        try:
            import akshare as ak

            # 获取财经新闻
            df = ak.stock_news_em(symbol="财经")

            if df is None or df.empty:
                self.logger.log("AKShare 返回空数据", "WARNING")
                return []

            news_list = []
            for _, row in df.iterrows():
                title = str(row.get("新闻标题", "")).strip()
                link = str(row.get("新闻链接", "")).strip()
                pub_date = str(row.get("发布时间", "")).strip()
                source = str(row.get("新闻来源", "东方财富")).strip()
                content = str(row.get("新闻内容", "")).strip()

                if not title or not link:
                    continue

                # 标准化时间格式
                if pub_date:
                    try:
                        # 尝试解析各种时间格式
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m-%d %H:%M"]:
                            try:
                                dt = datetime.strptime(pub_date[:19], fmt)
                                pub_date = dt.strftime("%Y-%m-%d %H:%M:%S")
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                news_list.append({
                    "title": title[:100],
                    "source": source or "东方财富",
                    "pub_date": pub_date,
                    "link": link,
                    "article": content[:5000],
                    "category": "财经",
                })

            return news_list

        except Exception as e:
            self.logger.log(f"获取新闻失败：{e}", "ERROR")
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
        爬取新闻

        Args:
            pages: 爬取次数（AKShare接口每次返回约10条）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        self.logger.log(f"开始爬取东方财富新闻，计划调用{pages}次...")

        for i in range(pages):
            news_list = self.fetch_news()

            if not news_list:
                self.logger.log(f"第{i+1}次调用无数据", "INFO")
                break

            inserted = self.save_news(news_list)
            total_inserted += inserted
            self.logger.log(f"第{i+1}次：获取{len(news_list)}条，新增{inserted}条")

            # AKShare接口有限流，不需要额外延迟
            if inserted == 0:
                self.logger.log("无新数据，停止爬取", "INFO")
                break

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = EastMoneyNewsCrawler()
    crawler.crawl(pages=3)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source LIKE "%东方财富%"')
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
