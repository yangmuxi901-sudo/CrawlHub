"""News architecture core: adapters -> normalize -> storage pipeline."""

from .models import NormalizedNewsItem
from .normalizer import normalize_news_item
from .storage import FinanceNewsStore
from .pipeline import NewsIngestionPipeline

