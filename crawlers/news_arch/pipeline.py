from __future__ import annotations

from typing import Any, Callable, Iterable

from .models import NormalizedNewsItem
from .storage import FinanceNewsStore


class NewsIngestionPipeline:
    """
    Three-layer pipeline:
    1) adapter fetches raw dicts
    2) normalizer maps raw -> NormalizedNewsItem
    3) storage persists normalized records
    """

    def __init__(self, store: FinanceNewsStore):
        self.store = store

    def ingest(
        self,
        raw_items: Iterable[dict[str, Any]],
        mapper: Callable[[dict[str, Any]], NormalizedNewsItem | None],
    ) -> tuple[int, int]:
        mapped: list[NormalizedNewsItem] = []
        raw_count = 0
        for raw in raw_items:
            raw_count += 1
            item = mapper(raw)
            if item is not None:
                mapped.append(item)
        inserted = self.store.save_batch(mapped)
        return raw_count, inserted

