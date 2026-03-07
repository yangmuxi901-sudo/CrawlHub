#!/usr/bin/env python
# -*- coding: utf-8 -*-

from crawlers.news_arch.normalizer import normalize_news_item


def test_normalize_news_item_minimal():
    item = normalize_news_item(
        source="测试源",
        title="测试标题",
        link="https://example.com/a",
        pub_date="2026-03-07T12:00:00+08:00",
        article="正文",
    )
    assert item is not None
    assert item.source == "测试源"
    assert item.link == "https://example.com/a"
    assert item.pub_date.startswith("2026-03-07 12:00:00")


def test_normalize_news_item_missing_required_returns_none():
    assert normalize_news_item(source="x", title="", link="https://example.com", pub_date="") is None
    assert normalize_news_item(source="x", title="ok", link="", pub_date="") is None
