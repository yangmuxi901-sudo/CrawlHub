#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上海证券报爬虫 - 简化版
基于 JustSimpleSpider/ShangHaiSecuritiesNews/cn_hongguan.py 改造
"""

import os
import sys
import json
import time
import sqlite3
import re
from datetime import datetime
from typing import List, Dict
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class CNStockCrawler(BaseCrawler):
    """上海证券报爬虫"""

    def __init__(self):
        super().__init__(name="CNStock")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36",
            "Referer": "http://news.cnstock.com/news/sns_yw/index.html",
        }
        self.list_url = "http://app.cnstock.com/api/waterfall?"
        # 主题列表：要闻、公司、市场、科创板等
        self.topic_list = [
            'qmt-sns_yw',     # 要闻 - 宏观
            'qmt-sns_jg',     # 要闻 - 金融
            "qmt-scp_gsxw",   # 公司 - 公司聚焦
            "qmt-tjd_ggkx",   # 公司 - 公告快讯
            "qmt-tjd_bbdj",   # 公司 - 公告解读
            "qmt-smk_gszbs",  # 市场 - 直播
            "qmt-sx_xgjj",    # 市场 - 新股聚焦
            "qmt-sx_zcdt",    # 市场 - 政策动态
            "qmt-smk_jjdx",   # 市场 - 基金
            "qmt-sns_qy",     # 市场 - 券业
            "qmt-skc_tt",     # 科创板 - 要闻
            "qmt-skc_jgfx",   # 科创板 - 监管
        ]

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT DEFAULT '上海证券报',
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

    def make_query_params(self, topic: str, page: int) -> Dict:
        """拼接动态请求参数"""
        import random
        import string

        query_params = {
            'colunm': topic,
            'page': str(page),   # 最大 50 页
            'num': str(10),
            'showstock': str(0),
            'callback': 'jQuery{}_{}'.format(
                ''.join(random.choice(string.digits) for _ in range(20)),
                str(int(time.time() * 1000))
            ),
            '_': str(int(time.time() * 1000)),
        }
        return query_params

    def get_list(self, topic: str, page: int) -> List[Dict]:
        """获取新闻列表"""
        params = self.make_query_params(topic, page)
        url = self.list_url + "&" + "&".join(f"{k}={v}" for k, v in params.items())

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            ret = resp.text

            # 解析 JSONP 响应
            match = re.search(r'jQuery\d+_\d+\((\{.*?\})\)', ret)
            if not match:
                return []

            json_str = match.group(1)
            py_data = json.loads(json_str)
            datas = py_data.get("data", {}).get("item", [])

            if not datas:
                return []

            items = []
            for one in datas:
                pub_date_str = one.get("time", "")
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    continue

                title = one.get("title", "")
                link = one.get("link", "")

                # 获取详情内容
                article = self.get_detail(link) if link else ""

                items.append({
                    'pub_date': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'title': title[:120],
                    'link': link,
                    'article': article or ""
                })

            return items

        except Exception as e:
            self.logger.log(f"获取列表失败 [{topic}]: {e}", "ERROR")
            return []

    def get_detail(self, detail_url: str) -> str:
        """获取新闻详情内容"""
        if not detail_url:
            return ""

        try:
            resp = requests.get(detail_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            page = resp.text

            # 简单提取正文内容（使用正则提取主要段落）
            # 实际项目中可使用 gne 等通用提取器
            content_match = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>', page, re.DOTALL)
            if content_match:
                # 去除 HTML 标签
                content = re.sub(r'<[^>]+>', '', content_match.group(1))
                return content.strip()

            return ""

        except Exception as e:
            self.logger.log(f"获取详情失败：{detail_url} - {e}", "DEBUG")
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
                    '上海证券报',
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
            pages: 每个主题爬取页数（每页 10 条）

        Returns:
            新增新闻数量
        """
        self.init_db()

        total_inserted = 0
        self.logger.log(f"开始爬取上海证券报，共{len(self.topic_list)}个主题...")

        for topic in self.topic_list:
            topic_items = []
            for page in range(1, pages + 1):
                page_items = self.get_list(topic, page)
                topic_items.extend(page_items)
                time.sleep(0.5)  # 避免请求过快

                # 如果某页没有数据，停止该主题
                if not page_items:
                    break

            if topic_items:
                inserted = self.save_news(topic_items)
                total_inserted += inserted
                self.logger.log(f"主题 {topic}: 获取{len(topic_items)}条，新增{inserted}条")

            time.sleep(1)  # 主题间延迟

        self.logger.log(f"爬取完成，共新增{total_inserted}条新闻")
        return total_inserted


def main():
    """独立运行"""
    crawler = CNStockCrawler()
    crawler.crawl(pages=3)

    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM finance_news WHERE source="上海证券报"')
    total = cursor.fetchone()[0]

    cursor.execute('''
        SELECT source, COUNT(*), MAX(pub_date)
        FROM finance_news
        GROUP BY source
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("上海证券报爬取结果")
    print("=" * 50)
    print(f"上海证券报总数：{total} 条")
    print("\n按来源统计:")
    for stat in stats:
        print(f"  {stat[0]}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
