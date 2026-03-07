#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrawlHub 管理 API
提供调度服务运行日志查询接口
"""

import os
import sys
import sqlite3
import json
import yaml
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
WEB_DIR = os.path.join(BASE_DIR, "web")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config", "scheduler.yaml")

JOB_LABELS = {
    "chemical_price": "化工价格",
    "chemical_utilization": "化工开工率",
    "ak_irm": "互动平台问答",
    "ir_pdf": "IR 纪要 PDF",
    "news_cls": "财联社电报",
    "news_yicai": "第一财经",
    "news_gov_stats": "国家统计局",
    "news_pbc": "中国人民银行",
    "news_sohu": "搜狐财经",
    "news_cnstock": "上海证券报",
    "news_hkex": "港交所新闻",
    "cls_reference": "财联社深度",
    "stcn_kuaixun": "证券时报快讯",
    "cninfo_announcement": "巨潮资讯公告",
    "eastmoney_news": "东方财富新闻",
    "news_juhe_domestic": "聚合新闻(Juhe)",
    "news_tianapi_domestic": "聚合新闻(TianAPI)",
}


def load_scheduler_jobs(config_path=DEFAULT_CONFIG_PATH):
    """读取调度配置中的 jobs"""
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return (data.get("scheduler") or {}).get("jobs") or {}
    except Exception:
        return {}


def get_source_health_summary(db_path=DB_PATH, config_path=DEFAULT_CONFIG_PATH, days=7):
    """汇总各任务源健康度"""
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 7
    if days <= 0:
        days = 7

    configured_jobs = load_scheduler_jobs(config_path)
    stats_by_job = {}
    latest_by_job = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                job_name,
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success_runs,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_runs,
                SUM(CASE WHEN status='success' AND COALESCE(records_count, 0)=0 THEN 1 ELSE 0 END) AS empty_runs,
                COALESCE(SUM(records_count), 0) AS total_records,
                MAX(start_time) AS last_run
            FROM scheduler_run_log
            WHERE datetime(start_time) >= datetime('now', ?)
            GROUP BY job_name
            """,
            (f"-{days} days",),
        )
        for row in cursor.fetchall():
            stats_by_job[row[0]] = {
                "total_runs": int(row[1] or 0),
                "success_runs": int(row[2] or 0),
                "failed_runs": int(row[3] or 0),
                "empty_runs": int(row[4] or 0),
                "total_records": int(row[5] or 0),
                "last_run": row[6] or "",
            }

        cursor.execute(
            """
            SELECT l.job_name, l.status, l.error_msg
            FROM scheduler_run_log l
            JOIN (
                SELECT job_name, MAX(id) AS max_id
                FROM scheduler_run_log
                GROUP BY job_name
            ) t
            ON l.job_name = t.job_name AND l.id = t.max_id
            """
        )
        for row in cursor.fetchall():
            latest_by_job[row[0]] = {
                "last_status": row[1] or "",
                "last_error": row[2] or "",
            }
    except sqlite3.OperationalError:
        # 兼容首次运行：日志表可能尚未创建
        pass
    finally:
        conn.close()

    job_names = sorted(set(configured_jobs.keys()) | set(stats_by_job.keys()))
    rows = []
    for job_name in job_names:
        cfg = configured_jobs.get(job_name, {})
        stat = stats_by_job.get(job_name, {})
        latest = latest_by_job.get(job_name, {})

        total_runs = int(stat.get("total_runs", 0))
        success_runs = int(stat.get("success_runs", 0))
        failed_runs = int(stat.get("failed_runs", 0))
        empty_runs = int(stat.get("empty_runs", 0))
        total_records = int(stat.get("total_records", 0))
        success_rate = round((success_runs / total_runs * 100), 1) if total_runs else 0.0
        empty_rate = round((empty_runs / max(success_runs, 1) * 100), 1) if success_runs else 0.0
        avg_records = round((total_records / total_runs), 1) if total_runs else 0.0
        enabled = bool(cfg.get("enabled", False))
        last_status = latest.get("last_status", "")

        if not enabled:
            health_status = "disabled"
        elif total_runs == 0:
            health_status = "no_data"
        elif success_rate >= 80 and last_status != "failed" and empty_rate < 60:
            health_status = "healthy"
        elif success_rate >= 50:
            health_status = "warning"
        else:
            health_status = "critical"

        rows.append(
            {
                "job_name": job_name,
                "label": JOB_LABELS.get(job_name, job_name),
                "enabled": enabled,
                "cron": cfg.get("cron", ""),
                "total_runs": total_runs,
                "success_runs": success_runs,
                "failed_runs": failed_runs,
                "empty_runs": empty_runs,
                "success_rate": success_rate,
                "empty_rate": empty_rate,
                "total_records": total_records,
                "avg_records": avg_records,
                "last_run": stat.get("last_run", ""),
                "last_status": last_status,
                "last_error": latest.get("last_error", ""),
                "health_status": health_status,
            }
        )

    return rows


class DashboardHandler(SimpleHTTPRequestHandler):
    """管理面板 API + 静态文件服务"""

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API 路由
        if path == '/api/stats':
            self.send_json(self.get_stats())
        elif path == '/api/logs':
            limit = int(query.get('limit', [20])[0])
            self.send_json(self.get_logs(limit))
        elif path == '/api/jobs':
            self.send_json(self.get_jobs())
        elif path == '/api/news-stats':
            self.send_json(self.get_news_stats())
        elif path == '/api/announcements':
            exchange = query.get('exchange', [None])[0]
            limit = int(query.get('limit', [50])[0])
            self.send_json(self.get_announcements(exchange, limit))
        elif path == '/api/source-health':
            days = int(query.get('days', [7])[0])
            self.send_json({"days": days, "items": self.get_source_health(days)})
        elif path == '/':
            self.serve_file(os.path.join(WEB_DIR, 'dashboard.html'))
        else:
            # 静态文件服务
            file_path = os.path.join(WEB_DIR, path.lstrip('/'))
            if os.path.exists(file_path):
                self.serve_file(file_path)
            else:
                self.send_error(404, 'Not Found')

    def get_stats(self):
        """获取统计数据"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 总执行次数
        cursor.execute("SELECT COUNT(*) FROM scheduler_run_log")
        total_runs = cursor.fetchone()[0]

        # 成功/失败次数
        cursor.execute("SELECT status, COUNT(*) FROM scheduler_run_log GROUP BY status")
        status_counts = dict(cursor.fetchall())

        # 总记录数
        cursor.execute("SELECT COALESCE(SUM(records_count), 0) FROM scheduler_run_log WHERE status='success'")
        total_records = cursor.fetchone()[0]

        # 今日数据
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(records_count), 0)
            FROM scheduler_run_log
            WHERE date(start_time) = date('now')
        """)
        today = cursor.fetchone()

        conn.close()

        return {
            "total_runs": total_runs,
            "success_runs": status_counts.get("success", 0),
            "failed_runs": status_counts.get("failed", 0),
            "total_records": total_records,
            "today_runs": today[0],
            "today_records": today[1],
        }

    def get_logs(self, limit=20):
        """获取执行日志"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT job_name, status, start_time, end_time, records_count, error_msg
            FROM scheduler_run_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "job_name": row[0],
                "status": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "records_count": row[4],
                "error_msg": row[5],
            }
            for row in rows
        ]

    def get_jobs(self):
        """获取任务配置"""
        jobs_cfg = load_scheduler_jobs()
        jobs = {}
        for job_name, cfg in jobs_cfg.items():
            jobs[job_name] = {
                "label": JOB_LABELS.get(job_name, job_name),
                "enabled": bool(cfg.get("enabled", False)),
                "cron": cfg.get("cron", ""),
            }
        return jobs

    def get_news_stats(self):
        """获取新闻统计数据"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT source, COUNT(*) as count, MAX(pub_date) as latest
            FROM finance_news
            GROUP BY source
            ORDER BY count DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "source": row[0],
                "count": row[1],
                "latest": row[2],
            }
            for row in rows
        ]

    def get_announcements(self, exchange=None, limit=50):
        """获取交易所公告"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if exchange and exchange != 'all':
            cursor.execute("""
                SELECT exchange, security_code, security_name, title, pub_date, category, link
                FROM exchange_announcements
                WHERE exchange = ?
                ORDER BY pub_date DESC
                LIMIT ?
            """, (exchange, limit))
        else:
            cursor.execute("""
                SELECT exchange, security_code, security_name, title, pub_date, category, link
                FROM exchange_announcements
                ORDER BY pub_date DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "exchange": row[0],
                "security_code": row[1],
                "security_name": row[2],
                "title": row[3],
                "pub_date": row[4],
                "category": row[5],
                "link": row[6],
            }
            for row in rows
        ]

    def get_source_health(self, days=7):
        """获取数据源健康度"""
        return get_source_health_summary(DB_PATH, DEFAULT_CONFIG_PATH, days)

    def send_json(self, data):
        """发送 JSON 响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def serve_file(self, file_path):
        """服务静态文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.send_response(200)
            if file_path.endswith('.html'):
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif file_path.endswith('.css'):
                self.send_header('Content-Type', 'text/css')
            elif file_path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))


def run_server(port=8080):
    """启动管理面板服务"""
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"管理面板已启动：http://localhost:{port}")
    print(f"API 地址：http://localhost:{port}/api/stats, /api/logs, /api/jobs")
    server.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CrawlHub 管理面板")
    parser.add_argument("--port", type=int, default=8080, help="服务端口")
    args = parser.parse_args()
    run_server(args.port)
