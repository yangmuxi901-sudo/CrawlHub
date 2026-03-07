from __future__ import annotations

import sqlite3
from typing import Iterable

from .models import NormalizedNewsItem


class FinanceNewsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finance_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT,
                pub_date TEXT,
                link TEXT,
                article TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(link)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_pub_date ON finance_news(pub_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_source ON finance_news(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_category ON finance_news(category)")
        conn.commit()
        conn.close()

    def save_batch(self, items: Iterable[NormalizedNewsItem]) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        inserted = 0
        for item in items:
            cur.execute(
                """
                INSERT OR IGNORE INTO finance_news
                (title, source, pub_date, link, article, category)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item.title, item.source, item.pub_date, item.link, item.article, item.category),
            )
            if cur.rowcount > 0:
                inserted += 1
        conn.commit()
        conn.close()
        return inserted

