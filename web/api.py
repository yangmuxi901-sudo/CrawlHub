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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
WEB_DIR = os.path.join(BASE_DIR, "web")


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
        return {
            # 爬虫任务
            "chemical_price": {
                "label": "化工价格",
                "enabled": True,
                "cron": "30 9,18 * * 1-5",
            },
            "chemical_utilization": {
                "label": "化工开工率",
                "enabled": True,
                "cron": "30 18 * * 1-5",
            },
            # 互动平台任务
            "ak_irm": {
                "label": "互动平台问答",
                "enabled": True,
                "cron": "0 2 * * *",
            },
            "ir_pdf": {
                "label": "IR 纪要 PDF",
                "enabled": True,
                "cron": "0 3 * * *",
            },
            # 新闻爬取任务
            "news_cls": {
                "label": "财联社电报",
                "enabled": True,
                "cron": "*/10 9-16 * * 1-5",
            },
            "news_yicai": {
                "label": "第一财经",
                "enabled": True,
                "cron": "*/15 9-17 * * 1-5",
            },
            "news_gov_stats": {
                "label": "国家统计局",
                "enabled": True,
                "cron": "0 10 * * 1-5",
            },
            "news_pbc": {
                "label": "中国人民银行",
                "enabled": True,
                "cron": "0 11 * * 1-5",
            },
            "news_sohu": {
                "label": "搜狐财经",
                "enabled": False,
                "cron": "0 15 * * 1-5",
            },
            # 新增金融数据源
            "news_cnstock": {
                "label": "上海证券报",
                "enabled": True,
                "cron": "0 9,15 * * 1-5",
            },
            "news_hkex": {
                "label": "港交所新闻",
                "enabled": True,
                "cron": "*/30 9-18 * * 1-5",
            },
        }

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
