#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
财联社电报爬虫 - 简化版
无需 MySQL 配置，直接使用 SQLite
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger
import time


class CLSTelegraphCrawler(BaseCrawler):
    """财联社电报爬虫"""

    def __init__(self):
        super().__init__(name="CLSTelegraph")
        self.web_url = 'https://www.cls.cn/telegraph'
        self.api_url = 'https://www.cls.cn/nodeapi/telegraphList'
        self.params = {
            'app': 'CailianpressWeb',
            'category': '',
            'lastTime': '',
            'last_time': '',
            'os': 'web',
            'refresh_type': '1',
            'rn': '20',
            'sv': '7.2.2',
            'sign': '831bc324f5ad2f1119379cfc5b7ca0f0'
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.cls.cn/',
        }

    def init_db(self):
        """初始化新闻表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT DEFAULT '财联社',
                pub_date TEXT,
                link TEXT,
                article TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(title, pub_date)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def fetch_news(self, last_time: int = None) -> tuple:
        """获取新闻列表"""
        import requests

        if last_time is None:
            last_time = int(time.time())

        # 使用更新的 sign 参数（从浏览器获取）
        self.params['lastTime'] = str(last_time)
        self.params['last_time'] = str(last_time)
        self.params['sign'] = self._generate_sign(last_time)

        try:
            resp = requests.get(self.api_url, params=self.params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # 尝试不同的响应格式
            roll_data = None
            if data.get('data') and isinstance(data.get('data'), dict):
                roll_data = data.get('data', {}).get('roll_data', [])
            elif data.get('data') and isinstance(data.get('data'), list):
                roll_data = data.get('data', [])

            if not roll_data:
                # 尝试直接获取首页新闻（不需要 last_time）
                return self._fetch_homepage_news()

            news_list = []
            for item in roll_data:
                title = item.get('title', '') or item.get('content', '')[:30]
                content = item.get('content', '')
                pub_time = item.get('ctime', 0)

                news_list.append({
                    'title': title[:60],
                    'source': '财联社',
                    'pub_date': datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'link': f"https://www.cls.cn/detail/{item.get('id', '')}",
                    'article': content
                })

            last_ctime = roll_data[-1].get('ctime', last_time)
            return news_list, last_ctime

        except Exception as e:
            self.logger.log(f"获取新闻失败：{e}", "ERROR")
            # 降级方案：尝试首页新闻
            return self._fetch_homepage_news()

    def _generate_sign(self, timestamp: int) -> str:
        """生成请求签名（简化版）"""
        import hashlib
        # 这是一个简化的签名生成，实际需要根据网站算法更新
        sign_str = f"CailianpressWeb{timestamp}"
        return hashlib.md5(sign_str.encode()).hexdigest()[:32]

    def _fetch_homepage_news(self) -> tuple:
        """备用方案：从首页获取新闻"""
        import requests

        try:
            # 使用移动端 API（更简单）
            mobile_url = "https://www.cls.cn/api/node/roll"
            params = {
                'app': 'CailianpressWeb',
                'client': 'web',
                'os': 'web',
                'sv': '7.2.2',
                'rn': '20',
            }
            resp = requests.get(mobile_url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get('code') == 200 and data.get('data'):
                roll_data = data.get('data', {}).get('roll_data', []) or data.get('data', [])

                news_list = []
                for item in roll_data[:20]:
                    title = item.get('title', '') or item.get('content', '')[:30]
                    content = item.get('content', '')
                    pub_time = item.get('ctime', int(time.time()))

                    news_list.append({
                        'title': title[:60],
                        'source': '财联社',
                        'pub_date': datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M:%S'),
                        'link': f"https://www.cls.cn/detail/{item.get('id', '')}",
                        'article': content
                    })

                if news_list:
                    last_ctime = news_list[-1].get('pub_date', '')
                    return news_list, last_ctime

            return [], ''

        except Exception as e:
            self.logger.log(f"首页新闻获取失败：{e}", "ERROR")
            return [], ''

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
                    news['article']
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                self.logger.log(f"插入失败：{e}", "DEBUG")

        conn.commit()
        conn.close()
        return inserted

    def crawl(self, pages: int = 5) -> int:
        """
        爬取新闻

        Args:
            pages: 爬取页数（每页 20 条）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        last_time = int(time.time())

        self.logger.log(f"开始爬取财联社电报，计划爬取{pages}页...")

        for page in range(pages):
            result = self.fetch_news(last_time)

            if not result or not result[0]:
                self.logger.log(f"第{page + 1}页无数据，停止爬取", "INFO")
                break

            news_list, last_time = result
            inserted = self.save_news(news_list)
            total_inserted += inserted

            self.logger.log(f"第{page + 1}页：获取{len(news_list)}条，新增{inserted}条")

            # 如果新增为 0，说明没有新数据了
            if inserted == 0:
                self.logger.log("无新数据，停止爬取", "INFO")
                break

            time.sleep(1)  # 避免请求过快

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻", "SUCCESS")
        return total_inserted


def main():
    """独立运行"""
    crawler = CLSTelegraphCrawler()
    crawler.crawl(pages=5)

    # 显示统计
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
    print("财联社电报爬取结果")
    print("=" * 50)
    print(f"新闻总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
