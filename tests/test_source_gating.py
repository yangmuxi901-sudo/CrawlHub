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


def _create_db_with_source(db_path, source_name):
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
            source_name,
            "2026-03-08 09:30:00",
            "https://example.com/news/1",
            "正文",
            "news",
        ),
    )
    conn.commit()
    conn.close()


def test_l2_source_is_admitted_and_has_level(monkeypatch):
    workdir = _workspace_tmp_dir("l2")
    db_path = workdir / "sync_record.db"
    _create_db_with_source(db_path, "财联社")
    monkeypatch.setattr(event_exporter, "DB_PATH", str(db_path))
    try:
        exporter = event_exporter.EventExporter(batch_id="20260308_110000")
        exporter.watermark_mgr = DummyWatermarkManager()
        events = exporter.fetch_events_from_db()

        assert len(events) == 1
        event = events[0]
        assert event["source_level"] == 2
        assert event["admission_status"] == "accepted"
        assert event["reject_reason"] == ""
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_l3_source_is_rejected_from_main_flow(monkeypatch):
    workdir = _workspace_tmp_dir("l3")
    db_path = workdir / "sync_record.db"
    _create_db_with_source(db_path, "聚合-Juhe")
    monkeypatch.setattr(event_exporter, "DB_PATH", str(db_path))
    try:
        exporter = event_exporter.EventExporter(batch_id="20260308_120000")
        exporter.watermark_mgr = DummyWatermarkManager()
        events = exporter.fetch_events_from_db()

        assert len(events) == 0
        assert len(exporter.rejected_events) == 1
        assert exporter.rejected_events[0]["admission_status"] == "rejected"
        assert exporter.rejected_events[0]["reject_reason"] == "source_level_l3_restricted"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
