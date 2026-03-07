#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3

from crawlers.news_domestic_aggregator import DomesticAggregatorCrawler
import crawlers.news_domestic_aggregator as agg


def test_fetch_juhe_without_key_returns_empty(monkeypatch):
    monkeypatch.delenv("JUHE_API_KEY", raising=False)
    crawler = DomesticAggregatorCrawler()
    rows = crawler._fetch_juhe(page=1, page_size=10)
    assert rows == []


def test_fetch_tianapi_without_key_returns_empty(monkeypatch):
    monkeypatch.delenv("TIANAPI_API_KEY", raising=False)
    crawler = DomesticAggregatorCrawler()
    rows = crawler._fetch_tianapi(num=10)
    assert rows == []


def test_save_news_inserts_unique_links(tmp_path, monkeypatch):
    db_path = tmp_path / "news_test.db"
    real_connect = sqlite3.connect

    def _connect(_ignored):
        return real_connect(db_path)

    monkeypatch.setattr(agg.sqlite3, "connect", _connect)
    crawler = DomesticAggregatorCrawler()
    crawler.init_db()

    sample = [
        {
            "title": "A",
            "source": "聚合-Juhe",
            "pub_date": "2026-03-07 10:00:00",
            "link": "https://example.com/a",
            "article": "x",
        },
        {
            "title": "A-dup",
            "source": "聚合-Juhe",
            "pub_date": "2026-03-07 10:00:01",
            "link": "https://example.com/a",
            "article": "y",
        },
    ]

    inserted = crawler.save_news(sample)
    assert inserted == 1

    conn = real_connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM finance_news")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 1
