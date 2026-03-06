#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
巨潮资讯网爬虫
爬取 A 股上市公司最新公告
数据源：http://webapi.cninfo.com.cn/
"""

import os
import sys
import json
import math
import time
import hashlib
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, DB_PATH, Logger


class CNInfoAnnouncementCrawler(BaseCrawler):
    """巨潮资讯网公告爬虫"""

    def __init__(self):
        super().__init__(name="CNInfo")
        self.api_base = "http://webapi.cninfo.com.cn/api/sysapi/"
        # 巨潮资讯 API 端点
        self.endpoints = {
            "zuixin": "p_sysapi1128",   # 最新公告
            "stock": "p_sysapi1078",    # 股票公告
            "fund": "p_sysapi1126",     # 基金公告
            "datas": "p_sysapi1127",    # 其他数据
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://webapi.cninfo.com.cn/",
            "mcode": self._generate_mcode(),
        }

    def _generate_mcode(self) -> str:
        """生成巨潮 API 所需的 mcode 参数"""
        dt = str(math.floor(time.time()))
        key_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        output = ""
        i = 0
        while i < len(dt):
            chr1 = ord(dt[i]) if i < len(dt) else 0
            chr2 = ord(dt[i+1]) if i+1 < len(dt) else 0
            chr3 = ord(dt[i+2]) if i+2 < len(dt) else 0
            i += 3

            enc1 = chr1 >> 2
            enc2 = ((chr1 & 3) << 4) | (chr2 >> 4)
            enc3 = ((chr2 & 15) << 2) | (chr3 >> 6)
            enc4 = chr3 & 63

            if not chr2:
                enc3 = enc4 = 64
            elif not chr3:
                enc4 = 64

            output += key_str[enc1] + key_str[enc2] + key_str[enc3] + key_str[enc4]
        return output

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS exchange_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                security_code TEXT NOT NULL,
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
        conn.execute('CREATE INDEX IF NOT EXISTS idx_announcements_code ON exchange_announcements(security_code)')
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    def fetch_announcements(self, api_name: str) -> List[Dict]:
        """获取公告列表"""
        url = self.api_base + api_name

        try:
            resp = requests.post(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("resultcode") != 200:
                self.logger.log(f"API 返回异常：{data.get('resultcode')}", "ERROR")
                return []

            records = data.get("records", [])
            return records

        except Exception as e:
            self.logger.log(f"获取公告失败：{e}", "ERROR")
            return []

    def process_records(self, records: List[Dict], exchange: str = "CNINFO") -> List[Dict]:
        """处理公告记录"""
        items = []
        for record in records:
            pub_date = record.get("DECLAREDATE") or record.get("RECTIME")
            if not pub_date:
                continue

            title = record.get("F001V", "")
            if not title:
                continue

            code = record.get("SECCODE", "")
            category = record.get("F003V", "")
            summary = record.get("F002V", "")

            items.append({
                "exchange": exchange,
                "security_code": code,
                "security_name": "",
                "title": title[:200],
                "pub_date": pub_date[:10] if len(pub_date) > 10 else pub_date,
                "category": category,
                "link": f"http://webapi.cninfo.com.cn/#/detail?code={code}",
                "content": summary[:1000] if summary else "",
            })

        return items

    def save_announcements(self, items: List[Dict]) -> int:
        """保存公告到数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        inserted = 0
        for item in items:
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

        total_inserted = 0
        self.logger.log("开始爬取巨潮资讯网公告...")

        # 爬取各类公告
        for name, endpoint in self.endpoints.items():
            self.logger.log(f"正在爬取：{name}...")
            records = self.fetch_announcements(endpoint)
            items = self.process_records(records)
            inserted = self.save_announcements(items)
            total_inserted += inserted
            self.logger.log(f"{name}: 获取{len(records)}条，新增{inserted}条")
            time.sleep(0.5)

        self.logger.log(f"爬取完成，共新增{total_inserted}条公告", "SUCCESS")
        return total_inserted


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
        SELECT category, COUNT(*), MAX(pub_date)
        FROM exchange_announcements
        WHERE exchange = 'CNINFO'
        GROUP BY category
        LIMIT 10
    ''')
    stats = cursor.fetchall()

    print("\n" + "=" * 50)
    print("巨潮资讯爬取结果")
    print("=" * 50)
    print(f"巨潮公告总数：{total} 条")
    print("\n按类别统计（前 10）:")
    for stat in stats:
        print(f"  {stat[0] or '未分类'}: {stat[1]} 条 (最新：{stat[2]})")

    conn.close()


if __name__ == "__main__":
    main()
