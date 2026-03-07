from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import NormalizedNewsItem


def _safe_time(text: str | None) -> str:
    if not text:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    value = str(text).strip().replace("T", " ").replace("Z", "")
    return value[:19]


def normalize_news_item(
    *,
    source: str,
    title: str,
    link: str,
    pub_date: str | None,
    article: str | None = "",
    category: str | None = "财经",
) -> NormalizedNewsItem | None:
    t = str(title or "").strip()
    u = str(link or "").strip()
    if not t or not u:
        return None
    return NormalizedNewsItem(
        title=t[:100],
        source=str(source or "unknown").strip() or "unknown",
        pub_date=_safe_time(pub_date),
        link=u,
        article=str(article or "").strip()[:10000],
        category=str(category or "财经").strip() or "财经",
    )


def from_juhe_record(record: dict[str, Any]) -> NormalizedNewsItem | None:
    return normalize_news_item(
        source="聚合-Juhe",
        title=record.get("title", ""),
        link=record.get("url", ""),
        pub_date=record.get("date"),
        article=record.get("author_name", ""),
        category="财经",
    )


def from_tianapi_record(record: dict[str, Any]) -> NormalizedNewsItem | None:
    return normalize_news_item(
        source="聚合-TianAPI",
        title=record.get("title", ""),
        link=record.get("url", ""),
        pub_date=record.get("ctime") or record.get("pubDate"),
        article=record.get("description") or record.get("content"),
        category="财经",
    )

