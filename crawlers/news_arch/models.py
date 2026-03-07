from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedNewsItem:
    title: str
    source: str
    pub_date: str
    link: str
    article: str
    category: str = "财经"

