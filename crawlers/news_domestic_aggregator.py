#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国内新闻聚合爬虫（Juhe + TianAPI）
目标：用聚合源替代大部分逐站点抓取，降低维护成本。

环境变量：
  JUHE_API_KEY            Juhe API Key
  JUHE_API_URL            默认: http://v.juhe.cn/toutiao/index
  JUHE_NEWS_TYPE          默认: caijing

  TIANAPI_API_KEY         TianAPI Key
  TIANAPI_API_URL         默认: https://apis.tianapi.com/caijing/index
  TIANAPI_WORD            关键词（可选）
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, List

import requests

from crawlers.base import BaseCrawler, DB_PATH


class DomesticAggregatorCrawler(BaseCrawler):
    """国内聚合新闻爬虫（Juhe + TianAPI）"""

    def __init__(self):
        super().__init__(name="DomesticAggregator")
        self.juhe_key = os.getenv("JUHE_API_KEY", "").strip()
        self.juhe_url = os.getenv("JUHE_API_URL", "http://v.juhe.cn/toutiao/index").strip()
        self.juhe_type = os.getenv("JUHE_NEWS_TYPE", "caijing").strip()

        self.tian_key = os.getenv("TIANAPI_API_KEY", "").strip()
        self.tian_url = os.getenv("TIANAPI_API_URL", "https://apis.tianapi.com/caijing/index").strip()
        self.tian_word = os.getenv("TIANAPI_WORD", "").strip()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/plain,*/*",
        }

    def init_db(self):
        """初始化统一新闻表"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT,
                pub_date TEXT,
                link TEXT,
                article TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(link)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)")
        conn.commit()
        conn.close()
        self.logger.log("数据库表初始化完成")

    @staticmethod
    def _safe_time(text: str | None) -> str:
        if not text:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = str(text).strip()
        # 兼容 2026-03-07T10:00:00+08:00 / 2026-03-07 10:00:00
        text = text.replace("T", " ").replace("Z", "")
        return text[:19]

    def _fetch_juhe(self, page: int = 1, page_size: int = 30) -> List[Dict]:
        if not self.juhe_key:
            self.logger.log("未配置 JUHE_API_KEY，跳过 Juhe 聚合", "WARNING")
            return []

        params = {
            "type": self.juhe_type,
            "page": page,
            "page_size": page_size,
            "key": self.juhe_key,
        }

        try:
            resp = requests.get(self.juhe_url, params=params, headers=self.headers, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("result", {}).get("data", [])
            if not isinstance(data, list):
                return []

            out: List[Dict] = []
            for item in data:
                title = str(item.get("title", "")).strip()
                link = str(item.get("url", "")).strip()
                if not title or not link:
                    continue
                out.append(
                    {
                        "title": title[:100],
                        "source": "聚合-Juhe",
                        "pub_date": self._safe_time(item.get("date")),
                        "link": link,
                        "article": str(item.get("author_name", "")).strip(),
                    }
                )
            return out
        except Exception as exc:
            self.logger.log(f"Juhe 获取失败：{exc}", "ERROR")
            return []

    def _fetch_tianapi(self, num: int = 30) -> List[Dict]:
        if not self.tian_key:
            self.logger.log("未配置 TIANAPI_API_KEY，跳过 TianAPI 聚合", "WARNING")
            return []

        params = {
            "key": self.tian_key,
            "num": str(num),
        }
        if self.tian_word:
            params["word"] = self.tian_word

        try:
            resp = requests.get(self.tian_url, params=params, headers=self.headers, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("result", {}).get("newslist", [])
            if not isinstance(rows, list):
                return []

            out: List[Dict] = []
            for item in rows:
                title = str(item.get("title", "")).strip()
                link = str(item.get("url", "")).strip()
                if not title or not link:
                    continue
                content = str(item.get("description", "") or item.get("content", "")).strip()
                out.append(
                    {
                        "title": title[:100],
                        "source": "聚合-TianAPI",
                        "pub_date": self._safe_time(item.get("ctime") or item.get("pubDate")),
                        "link": link,
                        "article": content[:10000],
                    }
                )
            return out
        except Exception as exc:
            self.logger.log(f"TianAPI 获取失败：{exc}", "ERROR")
            return []

    def save_news(self, news_list: List[Dict]) -> int:
        """保存新闻到数据库"""
        if not news_list:
            return 0

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        inserted = 0

        for news in news_list:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO finance_news
                    (title, source, pub_date, link, article)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        news["title"],
                        news["source"],
                        news["pub_date"],
                        news["link"],
                        news.get("article", ""),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as exc:
                self.logger.log(f"插入失败：{exc}", "DEBUG")

        conn.commit()
        conn.close()
        return inserted

    def crawl(self, provider: str = "all", pages: int = 1, page_size: int = 30) -> int:
        """
        provider: all | juhe | tianapi
        """
        self.init_db()
        provider = provider.strip().lower()
        if provider not in ("all", "juhe", "tianapi"):
            raise ValueError("provider must be one of: all/juhe/tianapi")

        total_inserted = 0

        if provider in ("all", "juhe"):
            for page in range(1, pages + 1):
                news = self._fetch_juhe(page=page, page_size=page_size)
                if not news:
                    break
                inserted = self.save_news(news)
                total_inserted += inserted
                self.logger.log(f"Juhe 第{page}页：获取{len(news)}条，新增{inserted}条")
                if inserted == 0:
                    break

        if provider in ("all", "tianapi"):
            news = self._fetch_tianapi(num=page_size)
            inserted = self.save_news(news)
            total_inserted += inserted
            self.logger.log(f"TianAPI：获取{len(news)}条，新增{inserted}条")

        self.logger.log(f"聚合新闻爬取完成，共新增{total_inserted}条", "SUCCESS")
        return total_inserted


def main():
    crawler = DomesticAggregatorCrawler()
    crawler.crawl(provider="all", pages=1, page_size=30)


if __name__ == "__main__":
    main()
