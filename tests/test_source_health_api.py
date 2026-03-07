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

import web.api as dashboard_api


def _workspace_tmp_dir(name):
    path = ROOT / "tests" / f".tmp_{name}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE scheduler_run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            error_msg TEXT,
            records_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        INSERT INTO scheduler_run_log (job_name, start_time, end_time, status, error_msg, records_count)
        VALUES ('news_cls', '2026-03-08 09:00:00', '2026-03-08 09:00:10', 'success', '', 20)
        """
    )
    conn.execute(
        """
        INSERT INTO scheduler_run_log (job_name, start_time, end_time, status, error_msg, records_count)
        VALUES ('news_cls', '2026-03-08 10:00:00', '2026-03-08 10:00:12', 'failed', 'timeout', 0)
        """
    )
    conn.commit()
    conn.close()


def _create_scheduler_yaml(path: Path):
    path.write_text(
        """
scheduler:
  jobs:
    news_cls:
      enabled: true
      cron: "*/10 9-16 * * 1-5"
    eastmoney_news:
      enabled: false
      cron: "0 9,12,17 * * 1-5"
""".strip(),
        encoding="utf-8",
    )


def test_source_health_summary_includes_enabled_and_disabled_jobs():
    tmp_path = _workspace_tmp_dir("source_health")
    try:
        db_path = tmp_path / "sync_record.db"
        cfg_path = tmp_path / "scheduler.yaml"
        _create_db(db_path)
        _create_scheduler_yaml(cfg_path)

        rows = dashboard_api.get_source_health_summary(
            db_path=str(db_path),
            config_path=str(cfg_path),
            days=7,
        )

        by_job = {row["job_name"]: row for row in rows}
        assert "news_cls" in by_job
        assert "eastmoney_news" in by_job

        assert by_job["news_cls"]["enabled"] is True
        assert by_job["news_cls"]["total_runs"] == 2
        assert by_job["news_cls"]["failed_runs"] == 1
        assert by_job["news_cls"]["last_status"] in ("failed", "success")

        assert by_job["eastmoney_news"]["enabled"] is False
        assert by_job["eastmoney_news"]["health_status"] == "disabled"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
