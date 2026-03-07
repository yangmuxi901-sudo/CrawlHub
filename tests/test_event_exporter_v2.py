#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import sys
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import storage.event_exporter as event_exporter


def _workspace_tmp_dir(name):
    path = ROOT / "tests" / f".tmp_{name}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class DummyWatermarkManager:
    def get_producer_watermark(self, source=None):
        return {}

    def update_producer_watermark(self, source, event_id, published_at):
        return None


def _create_news_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE finance_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            pub_date TEXT,
            link TEXT,
            article TEXT,
            category TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO finance_news (title, source, pub_date, link, article, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "测试新闻",
            "财联社",
            "2026-03-08 09:30:00",
            "https://example.com/news/1",
            "正文",
            "news",
        ),
    )
    conn.commit()
    conn.close()


def test_manifest_v2_fields_and_export_root_env(monkeypatch):
    workdir = _workspace_tmp_dir("manifest")
    export_root = workdir / "preopen_feed"
    monkeypatch.setenv("PREOPEN_EXPORT_ROOT", str(export_root))
    try:
        exporter = event_exporter.EventExporter(batch_id="20260308_080000")
        exporter.watermark_mgr = DummyWatermarkManager()
        exporter.events = [
            {
                "event_id": "e1",
                "source": "测试源",
                "source_id": "1",
                "title": "标题",
                "published_at": "2026-03-08T09:30:00+08:00",
                "url": "https://example.com/1",
                "event_type": "news",
                "ingested_at": "2026-03-08T09:31:00+08:00",
                "collected_at": "2026-03-08T09:31:00+08:00",
            }
        ]

        count = exporter.write_events_file()
        manifest = exporter.write_manifest(count)

        assert exporter.export_dir == str(export_root / "20260308_080000")
        assert manifest["schema_version"] == "2.0"
        assert manifest["batch_id"] == "20260308_080000"
        assert manifest["record_count"] == 1
        assert "generated_at" in manifest
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_format_timestamp_uses_iso8601_with_timezone():
    exporter = event_exporter.EventExporter(batch_id="20260308_090000")
    ts = exporter._format_timestamp("2026-03-08 09:30:00")
    assert "T" in ts
    assert ts.endswith("+08:00")


def test_fetch_events_keeps_legacy_fields_and_adds_collected_at(monkeypatch):
    workdir = _workspace_tmp_dir("db")
    db_path = workdir / "sync_record.db"
    _create_news_db(db_path)
    monkeypatch.setattr(event_exporter, "DB_PATH", str(db_path))
    try:
        exporter = event_exporter.EventExporter(batch_id="20260308_100000")
        exporter.watermark_mgr = DummyWatermarkManager()
        events = exporter.fetch_events_from_db()

        assert len(events) == 1
        event = events[0]

        assert "source_id" in event
        assert "event_type" in event
        assert "ingested_at" in event
        assert "collected_at" in event

        assert event["published_at"].endswith("+08:00")
        assert event["ingested_at"].endswith("+08:00")
        assert event["collected_at"].endswith("+08:00")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
