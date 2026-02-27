#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股东报告管理 API (FastAPI)
提供爬取任务管理、公司列表管理、统计数据等接口
"""

import os
import re
import sys
import json
import time
import sqlite3
import threading
import subprocess
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ============== 配置 ==============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PDF_DIR = os.path.join(DATA_DIR, "ir_pdfs")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
LOG_PATH = os.path.join(DATA_DIR, "download_log.txt")
COMPANY_LIST_PATH = os.path.join(BASE_DIR, "公司列表.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ============== 任务状态管理 ==============
class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    """爬取任务管理器"""

    def __init__(self):
        self.status = TaskStatus.IDLE
        self.progress = 0

        self.total = 0
        self.downloaded = 0
        self.current_company = ""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error_message = ""
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self.status = TaskStatus.RUNNING
            self.progress = 0

            # 动态读取公司列表总数
            self.total = self._get_company_count()
            self.downloaded = 0
            self.current_company = ""
            self.start_time = datetime.now()
            self.end_time = None
            self.error_message = ""

    def _get_company_count(self) -> int:
        """获取公司列表中的公司总数"""
        try:
            if os.path.exists(COMPANY_LIST_PATH):
                df = pd.read_csv(COMPANY_LIST_PATH)
                return len(df)
        except Exception:
            pass
        return 0  # 默认返回 0

    def update(self, progress: int, total: int, downloaded: int, current_company: str):
        with self._lock:
            self.progress = progress
            if total > 0:
                self.total = total
            self.downloaded = downloaded
            self.current_company = current_company

    def complete(self, downloaded: int):
        with self._lock:
            self.status = TaskStatus.COMPLETED
            self.downloaded = downloaded
            self.end_time = datetime.now()

    def fail(self, error: str):
        with self._lock:
            self.status = TaskStatus.FAILED
            self.error_message = error
            self.end_time = datetime.now()

    def reset(self):
        with self._lock:
            self.status = TaskStatus.IDLE
            self.progress = 0

            self.downloaded = 0
            self.current_company = ""
            self.error_message = ""

    def get_status(self) -> Dict:
        with self._lock:
            elapsed = None
            if self.start_time:
                end = self.end_time or datetime.now()
                elapsed = int((end - self.start_time).total_seconds())

            return {
                "status": self.status.value,
                "progress": self.progress,
                "total": self.total,
                "downloaded": self.downloaded,
                "current_company": self.current_company,
                "elapsed_seconds": elapsed,
                "error_message": self.error_message,
            }

task_manager = TaskManager()

# ============== FastAPI 应用 ==============
app = FastAPI(
    title="股东报告管理 API",
    description="A 股投资者关系活动记录表 PDF 下载器管理接口",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 静态文件服务 ==============
WEB_DIR = os.path.dirname(os.path.abspath(__file__))

# ============== 数据模型 ==============
class Company(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    industry_l1: Optional[str] = ""
    industry_l2: Optional[str] = ""
    industry_l3: Optional[str] = ""

class CompanyCreate(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    industry_l1: Optional[str] = ""
    industry_l2: Optional[str] = ""
    industry_l3: Optional[str] = ""

class ScheduleConfig(BaseModel):
    enabled: bool
    cron_expression: str  # cron 表达式，如 "0 9 * * 1-5" 表示工作日9点
    incremental: bool = True  # 是否增量下载

class StartTaskRequest(BaseModel):
    incremental: bool = True  # 是否增量下载
    reset_all: bool = False  # 是否重置所有公司的下载记录

# ============== 工具函数 ==============
def get_orgid_mapping() -> Dict[str, str]:
    """获取 orgId 映射表"""
    try:
        url = "https://www.cninfo.com.cn/new/data/szse_stock.json"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        data = resp.json()
        return {s['code']: s['orgId'] for s in data.get('stockList', [])}
    except:
        return {}

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_log_for_progress(log_content: str) -> Dict:
    """解析日志获取进度信息"""
    lines = log_content.strip().split('\n')

    progress = 0
    total = 0

    downloaded = 0
    current_company = ""

    for line in lines[-100:]:  # 只看最后100行
        # 匹配进度: [xxx/495]
        match = re.search(r'\[(\d+)/(\d+)\]', line)
        if match:
            progress = int(match.group(1))
            total = int(match.group(2))

        # 匹配当前公司
        match = re.search(r'\] 查询 (\S+) (\S+)', line)
        if match:
            current_company = f"{match.group(1)} {match.group(2)}"

        # 匹配下载完成
        if '完成：下载' in line:
            match = re.search(r'下载 (\d+) 份', line)
            if match:
                downloaded += int(match.group(1))

    return {
        "progress": progress,
        "total": total,
        "downloaded": downloaded,
        "current_company": current_company
    }

def run_download_task(incremental: bool = True, reset_all: bool = False):
    """运行下载任务（后台线程）"""
    global task_manager

    try:
        task_manager.start()

        # 如果需要重置
        if reset_all:
            conn = get_db_connection()
            conn.execute("DELETE FROM download_history")
            conn.commit()
            conn.close()

        # 动态导入并运行下载器
        sys.path.insert(0, BASE_DIR)

        # 使用子进程运行，避免阻塞
        cmd = [sys.executable, os.path.join(BASE_DIR, "standalone_ir_downloader.py")]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=BASE_DIR
        )
        task_manager.process = process

        # 监控进程和日志
        while process.poll() is None:
            time.sleep(2)

            # 读取日志获取进度
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                    info = parse_log_for_progress(content)
                    task_manager.update(
                        info["progress"],
                        info["total"],
                        info["downloaded"],
                        info["current_company"]
                    )

        # 检查结果
        if process.returncode == 0:
            # 获取最终统计
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                    info = parse_log_for_progress(content)
                    task_manager.complete(info["downloaded"])
            else:
                task_manager.complete(0)
        else:
            stderr = process.stderr.read().decode('utf-8') if process.stderr else ""
            task_manager.fail(stderr or "下载任务失败")

    except Exception as e:
        task_manager.fail(str(e))

# ============== API 路由 ==============

@app.get("/")
async def root():
    """API 根路径"""
    return {"message": "股东报告管理 API", "version": "1.0.0"}

@app.get("/ui", response_class=HTMLResponse)
async def get_ui():
    """获取独立版 UI 页面"""
    html_path = os.path.join(WEB_DIR, "index-standalone.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="UI 文件不存在")

# --------------- 任务管理 ---------------

@app.get("/task/status")
async def get_task_status():
    """获取当前任务状态"""
    return task_manager.get_status()

@app.post("/task/start")
async def start_task(request: StartTaskRequest, background_tasks: BackgroundTasks):
    """启动下载任务"""
    if task_manager.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="任务已在运行中")

    # 清空日志文件
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'w') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 任务启动\n")

    # 启动后台任务
    background_tasks.add_task(run_download_task, request.incremental, request.reset_all)

    return {"message": "任务已启动", "status": "running"}

@app.post("/task/stop")
async def stop_task():
    """停止下载任务"""
    if task_manager.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="没有运行中的任务")

    if task_manager.process:
        task_manager.process.terminate()
        task_manager.fail("用户手动停止")

    return {"message": "任务已停止"}

@app.post("/task/reset")
async def reset_task():
    """重置任务状态"""
    task_manager.reset()
    return {"message": "任务状态已重置"}

# --------------- 统计数据 ---------------

@app.get("/stats/overview")
async def get_stats_overview():
    """获取统计数据概览"""
    # 统计 PDF 数量
    total_pdfs = 0
    companies_with_files = 0
    company_stats = []

    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])
                if pdf_count > 0:
                    companies_with_files += 1
                    company_stats.append({
                        "ticker_folder": folder,
                        "count": pdf_count
                    })
                total_pdfs += pdf_count

    # 获取数据库中的记录数
    conn = get_db_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM download_history")
    db_records = cursor.fetchone()[0]

    # 获取最后下载时间
    cursor = conn.execute("SELECT MAX(last_publish_date) FROM download_history")
    last_download = cursor.fetchone()[0]
    conn.close()

    # 读取公司列表
    total_companies = 0
    if os.path.exists(COMPANY_LIST_PATH):
        df = pd.read_csv(COMPANY_LIST_PATH)
        total_companies = len(df)

    return {
        "total_companies": total_companies,
        "companies_with_files": companies_with_files,
        "companies_without_files": total_companies - companies_with_files,
        "total_pdfs": total_pdfs,
        "db_records": db_records,
        "last_download_date": last_download,
    }

@app.get("/stats/companies")
async def get_company_stats(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("count", pattern="^(count|ticker|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$")
):
    """获取公司文件统计列表"""
    company_stats = []

    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])

                # 解析 ticker 和公司名
                parts = folder.split("_", 1)
                ticker = parts[0] if parts else folder
                name = parts[1] if len(parts) > 1 else ""

                company_stats.append({
                    "ticker": ticker,
                    "company_name": name,
                    "pdf_count": pdf_count,
                })

    # 排序
    if sort_by == "count":
        company_stats.sort(key=lambda x: x["pdf_count"], reverse=(order == "desc"))
    elif sort_by == "ticker":
        company_stats.sort(key=lambda x: x["ticker"], reverse=(order == "desc"))
    elif sort_by == "name":
        company_stats.sort(key=lambda x: x["company_name"], reverse=(order == "desc"))

    # 分页
    total = len(company_stats)
    start = (page - 1) * page_size
    end = start + page_size
    items = company_stats[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

@app.get("/stats/distribution")
async def get_file_distribution():
    """获取文件数量分布"""
    distribution = {}

    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])
                if pdf_count > 0:
                    distribution[pdf_count] = distribution.get(pdf_count, 0) + 1

    return {
        "distribution": dict(sorted(distribution.items())),
    }

# --------------- 公司管理 ---------------

@app.get("/companies")
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exchange: Optional[str] = Query(None, pattern="^(sz|sh|bj)$"),
    search: Optional[str] = Query(None)
):
    """获取公司列表"""
    if not os.path.exists(COMPANY_LIST_PATH):
        raise HTTPException(status_code=404, detail="公司列表文件不存在")

    df = pd.read_csv(COMPANY_LIST_PATH)

    # 过滤
    if exchange:
        df = df[df['exchange'] == exchange]

    if search:
        mask = df['ticker'].str.contains(search, case=False, na=False) | \
               df['company_name'].str.contains(search, case=False, na=False)
        df = df[mask]

    # 获取本地文件数
    local_counts = {}
    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            if os.path.isdir(os.path.join(PDF_DIR, folder)):
                ticker = folder.split("_")[0]
                pdf_count = len([f for f in os.listdir(os.path.join(PDF_DIR, folder))
                               if f.endswith('.pdf') or f.endswith('.PDF')])
                local_counts[ticker] = pdf_count

    # 获取数据库记录
    conn = get_db_connection()
    cursor = conn.execute("SELECT ticker, last_publish_date FROM download_history")
    db_records = {row['ticker']: row['last_publish_date'] for row in cursor.fetchall()}
    conn.close()

    # 构建结果
    items = []
    for _, row in df.iterrows():
        items.append({
            "ticker": row['ticker'],
            "company_name": row['company_name'],
            "exchange": row['exchange'],
            "industry_l1": row.get('industry_l1', ''),
            "industry_l2": row.get('industry_l2', ''),
            "industry_l3": row.get('industry_l3', ''),
            "local_count": local_counts.get(row['ticker'], 0),
            "last_sync_date": db_records.get(row['ticker'], ''),
        })

    # 分页
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start:end],
    }

@app.post("/companies")
async def add_company(company: CompanyCreate):
    """添加公司"""
    if not os.path.exists(COMPANY_LIST_PATH):
        raise HTTPException(status_code=404, detail="公司列表文件不存在")

    df = pd.read_csv(COMPANY_LIST_PATH)

    # 检查是否已存在
    if company.ticker in df['ticker'].values:
        raise HTTPException(status_code=400, detail="公司已存在")

    # 添加新公司
    new_row = {
        'ticker': company.ticker,
        'company_name': company.company_name,
        'exchange': company.exchange,
        'industry_l1': company.industry_l1 or '',
        'industry_l2': company.industry_l2 or '',
        'industry_l3': company.industry_l3 or '',
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(COMPANY_LIST_PATH, index=False)

    return {"message": "公司添加成功", "company": new_row}

@app.delete("/companies/{ticker}")
async def delete_company(ticker: str):
    """删除公司"""
    if not os.path.exists(COMPANY_LIST_PATH):
        raise HTTPException(status_code=404, detail="公司列表文件不存在")

    df = pd.read_csv(COMPANY_LIST_PATH)

    if ticker not in df['ticker'].values:
        raise HTTPException(status_code=404, detail="公司不存在")

    df = df[df['ticker'] != ticker]
    df.to_csv(COMPANY_LIST_PATH, index=False)

    return {"message": "公司删除成功"}

# --------------- 日志 ---------------

@app.get("/logs")
async def get_logs(
    lines: int = Query(100, ge=1, le=1000),
    level: Optional[str] = Query(None, pattern="^(INFO|WARNING|ERROR)$")
):
    """获取日志"""
    if not os.path.exists(LOG_PATH):
        return {"logs": [], "message": "日志文件不存在"}

    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    log_lines = content.strip().split('\n')

    if level:
        log_lines = [l for l in log_lines if f'[{level}]' in l]

    # 返回最后 N 行
    result = log_lines[-lines:]

    return {
        "total": len(log_lines),
        "returned": len(result),
        "logs": result,
    }

@app.delete("/logs")
async def clear_logs():
    """清空日志"""
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 日志已清空\n")

    return {"message": "日志已清空"}

# --------------- 数据库管理 ---------------

@app.get("/database/records")
async def get_db_records():
    """获取数据库记录"""
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT ticker, last_publish_date
        FROM download_history
        ORDER BY last_publish_date DESC
    """)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"records": records, "total": len(records)}

@app.delete("/database/records/{ticker}")
async def delete_db_record(ticker: str):
    """删除单条数据库记录（用于重新下载）"""
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM download_history WHERE ticker = ?", (ticker,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="记录不存在")

    conn.execute("DELETE FROM download_history WHERE ticker = ?", (ticker,))
    conn.commit()
    conn.close()

    return {"message": f"已删除 {ticker} 的下载记录，可重新下载"}

@app.post("/database/reset")
async def reset_database():
    """重置整个数据库"""
    conn = get_db_connection()
    conn.execute("DELETE FROM download_history")
    conn.commit()
    conn.close()

    return {"message": "数据库已重置"}

# --------------- 文件操作 ---------------

@app.get("/files/browse")
async def browse_files(ticker: Optional[str] = None):
    """浏览文件"""
    if not os.path.exists(PDF_DIR):
        return {"folders": [], "files": []}

    if ticker:
        # 浏览特定公司的文件
        for folder in os.listdir(PDF_DIR):
            if folder.startswith(ticker + "_"):
                folder_path = os.path.join(PDF_DIR, folder)
                files = sorted(os.listdir(folder_path))
                return {
                    "folder": folder,
                    "files": files,
                    "count": len(files)
                }
        return {"folder": None, "files": [], "count": 0}
    else:
        # 浏览所有公司文件夹
        folders = []
        for folder in sorted(os.listdir(PDF_DIR)):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])
                folders.append({
                    "name": folder,
                    "pdf_count": pdf_count,
                })
        return {"folders": folders, "total": len(folders)}

@app.get("/files/download/{ticker}")
async def download_company_files(ticker: str):
    """下载公司所有文件（ZIP）"""
    import zipfile
    import io

    # 找到公司文件夹
    target_folder = None
    for folder in os.listdir(PDF_DIR):
        if folder.startswith(ticker + "_"):
            target_folder = folder
            break

    if not target_folder:
        raise HTTPException(status_code=404, detail="公司文件不存在")

    folder_path = os.path.join(PDF_DIR, target_folder)

    # 创建 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename in os.listdir(folder_path):
            if filename.endswith('.pdf') or filename.endswith('.PDF'):
                filepath = os.path.join(folder_path, filename)
                zipf.write(filepath, filename)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={ticker}_reports.zip"}
    )

@app.get("/files/preview/{ticker}/{filename:path}")
async def preview_pdf(ticker: str, filename: str):
    """预览 PDF 文件"""
    import urllib.parse

    # 找到公司文件夹
    target_folder = None
    for folder in os.listdir(PDF_DIR):
        if folder.startswith(ticker + "_"):
            target_folder = folder
            break

    if not target_folder:
        raise HTTPException(status_code=404, detail="公司文件不存在")

    file_path = os.path.join(PDF_DIR, target_folder, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 对中文文件名进行 URL 编码
    encoded_filename = urllib.parse.quote(filename)

    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"}
    )

# --------------- 检测新报告 ---------------

@app.get("/task/check_new")
async def check_new_reports():
    """检测有新报告的公司 - 使用模糊匹配方式"""
    import urllib.parse
    import re
    from datetime import datetime, timedelta

    # 获取最后下载日期
    conn = get_db_connection()
    cursor = conn.execute("SELECT MAX(last_publish_date) FROM download_history")
    last_date = cursor.fetchone()[0]
    conn.close()

    # 默认检查最近60天（扩大范围确保不遗漏）
    if last_date:
        start_date = datetime.strptime(last_date, '%Y-%m-%d') - timedelta(days=7)  # 多检查7天
    else:
        start_date = datetime.now() - timedelta(days=60)

    end_date = datetime.now()
    date_range = f"{start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}"

    # 获取本地文件信息：ticker -> set of dates
    local_dates = {}  # ticker -> set of YYYY-MM-DD dates
    local_files = {}  # ticker -> list of filenames
    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                ticker = folder.split("_")[0]
                files = os.listdir(folder_path)
                local_files[ticker] = files
                # 提取本地文件中的日期
                dates = set()
                for f in files:
                    # 匹配 YYYY-MM-DD 或 YYYYMMDD 格式
                    match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', f)
                    if match:
                        date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                        dates.add(date_str)
                local_dates[ticker] = dates

    # 读取公司列表用于匹配
    if not os.path.exists(COMPANY_LIST_PATH):
        raise HTTPException(status_code=404, detail="公司列表文件不存在")

    df = pd.read_csv(COMPANY_LIST_PATH)
    ticker_to_name = dict(zip(df['ticker'], df['company_name']))

    # 构建纯代码到完整ticker的映射
    pure_to_ticker = {}
    for t in df['ticker']:
        pure = t.split('.')[-1]
        pure_to_ticker[pure] = t

    # 存储候选新报告
    candidates = []  # [(ticker, date, title, sec_name), ...]

    # 批量查询 cninfo - 深交所
    try:
        url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
        params = {
            "searchkey": "投资者关系活动记录表",
            "pageNum": 1,
            "pageSize": 200,
            "column": "szse",
            "tabName": "fulltext",
            "seDate": date_range,
            "isHLtitle": "true",
        }
        headers = HEADERS.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        resp = requests.post(url, data=urllib.parse.urlencode(params),
                            headers=headers, timeout=20)
        data = resp.json()

        for ann in data.get('announcements', []):
            sec_code = ann.get('secCode', '')
            sec_name = ann.get('secName', '')
            title = ann.get('announcementTitle', '').replace('<em>', '').replace('</em>', '')

            # 从 adjunctUrl 提取公告日期
            adjunct_url = ann.get('adjunctUrl', '')
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', adjunct_url)
            if not date_match:
                # 从时间戳提取
                ts = ann.get('announcementTime', 0)
                if ts:
                    ann_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                else:
                    continue
            else:
                ann_date = date_match.group(1)

            # 匹配本地 ticker
            ticker = pure_to_ticker.get(sec_code)
            if not ticker:
                # 尝试不同前缀
                for prefix in ['sz.', 'sh.', 'bj.']:
                    if prefix + sec_code in ticker_to_name:
                        ticker = prefix + sec_code
                        break
            if not ticker:
                continue  # 不在监控列表中

            # 模糊匹配：检查该日期是否已在本地
            local_date_set = local_dates.get(ticker, set())
            if ann_date not in local_date_set:
                candidates.append({
                    "ticker": ticker,
                    "company_name": ticker_to_name.get(ticker, sec_name),
                    "exchange": ticker.split('.')[0] if '.' in ticker else 'sz',
                    "date": ann_date,
                    "title": title[:60],
                    "local_count": len(local_files.get(ticker, [])),
                    "status": "new_date"  # 新日期，可能是新报告
                })
    except Exception as e:
        print(f"查询深交所失败: {e}")

    # 批量查询 cninfo - 上交所
    try:
        params["column"] = "sse"
        resp = requests.post(url, data=urllib.parse.urlencode(params),
                            headers=headers, timeout=20)
        data = resp.json()

        for ann in data.get('announcements', []):
            sec_code = ann.get('secCode', '')
            sec_name = ann.get('secName', '')
            title = ann.get('announcementTitle', '').replace('<em>', '').replace('</em>', '')

            adjunct_url = ann.get('adjunctUrl', '')
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', adjunct_url)
            if not date_match:
                ts = ann.get('announcementTime', 0)
                if ts:
                    ann_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                else:
                    continue
            else:
                ann_date = date_match.group(1)

            ticker = f"sh.{sec_code}"
            if ticker not in ticker_to_name:
                ticker = pure_to_ticker.get(sec_code)
            if not ticker:
                continue

            local_date_set = local_dates.get(ticker, set())
            if ann_date not in local_date_set:
                candidates.append({
                    "ticker": ticker,
                    "company_name": ticker_to_name.get(ticker, sec_name),
                    "exchange": "sh",
                    "date": ann_date,
                    "title": title[:60],
                    "local_count": len(local_files.get(ticker, [])),
                    "status": "new_date"
                })
    except Exception as e:
        print(f"查询上交所失败: {e}")

    # 按公司聚合，但保留详细的候选列表
    company_new = {}  # ticker -> {info, reports: []}
    for c in candidates:
        ticker = c['ticker']
        if ticker not in company_new:
            company_new[ticker] = {
                "ticker": ticker,
                "company_name": c['company_name'],
                "exchange": c['exchange'],
                "local_count": c['local_count'],
                "new_count": 0,
                "reports": []
            }
        company_new[ticker]['new_count'] += 1
        company_new[ticker]['reports'].append({
            "date": c['date'],
            "title": c['title']
        })

    # 按新报告数排序
    results = sorted(company_new.values(), key=lambda x: (-x['new_count'], x['ticker']))

    return {
        "total": len(results),
        "total_new_reports": len(candidates),
        "date_range": date_range,
        "items": results[:50]  # 最多返回50家公司
    }

# --------------- 导出报告 ---------------

@app.get("/export/csv")
async def export_csv():
    """导出统计数据为 CSV"""
    import io

    company_stats = []

    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])

                parts = folder.split("_", 1)
                ticker = parts[0] if parts else folder
                name = parts[1] if len(parts) > 1 else ""

                company_stats.append({
                    "ticker": ticker,
                    "company_name": name,
                    "pdf_count": pdf_count,
                })

    df = pd.DataFrame(company_stats)

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=shareholder_reports_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@app.get("/export/json")
async def export_json():
    """导出完整统计数据为 JSON"""
    stats = await get_stats_overview()
    company_stats = []

    if os.path.exists(PDF_DIR):
        for folder in os.listdir(PDF_DIR):
            folder_path = os.path.join(PDF_DIR, folder)
            if os.path.isdir(folder_path):
                pdf_count = len([f for f in os.listdir(folder_path)
                               if f.endswith('.pdf') or f.endswith('.PDF')])

                parts = folder.split("_", 1)
                ticker = parts[0] if parts else folder
                name = parts[1] if len(parts) > 1 else ""

                company_stats.append({
                    "ticker": ticker,
                    "company_name": name,
                    "pdf_count": pdf_count,
                })

    export_data = {
        "export_time": datetime.now().isoformat(),
        "overview": stats,
        "companies": company_stats,
    }

    import json
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)

    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=shareholder_reports_{datetime.now().strftime('%Y%m%d')}.json"}
    )

# --------------- 健康检查 ---------------

# ============== 化工数据 API ==============
CHEMICAL_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHEMICAL_DB_PATH = DB_PATH  # 共用同一个 SQLite

# 化工爬取任务状态
chemical_crawl_status = {
    "status": "idle",
    "progress": 0,
    "message": "",
}


def _read_chemical_csv(filename):
    """读取化工 CSV 数据"""
    path = os.path.join(CHEMICAL_OUTPUT_DIR, filename)
    if os.path.exists(path):
        df = pd.read_csv(path, encoding="utf-8-sig")
        return df.fillna("").to_dict(orient="records")
    return []


@app.get("/chemical/prices")
async def get_chemical_prices(search: Optional[str] = None, category: Optional[str] = None):
    """获取化工产品价格数据"""
    records = _read_chemical_csv("chemical_prices.csv")
    if search:
        records = [r for r in records if search in r.get("product_name", "")]
    if category:
        records = [r for r in records if r.get("product_category") == category]
    return {"items": records, "total": len(records)}


@app.get("/chemical/utilization")
async def get_chemical_utilization():
    """获取化工开工率数据"""
    records = _read_chemical_csv("chemical_utilization.csv")
    return {"items": records, "total": len(records)}


@app.get("/chemical/stats")
async def get_chemical_stats():
    """获取化工数据统计"""
    prices = _read_chemical_csv("chemical_prices.csv")
    utils = _read_chemical_csv("chemical_utilization.csv")

    # 从配置获取产品总数
    config_path = os.path.join(BASE_DIR, "config", "products.yaml")
    total_products = 0
    total_categories = 0
    total_tickers = 0
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        products = cfg.get("products", [])
        total_products = len(products)
        total_categories = len(set(p["category"] for p in products))
        total_tickers = len(set(t for p in products for t in p.get("tickers", [])))
    except Exception:
        total_products = 46
        total_categories = 14
        total_tickers = 73

    # 最后爬取日期
    last_date = "-"
    if prices:
        dates = [r.get("trade_date", "") for r in prices if r.get("trade_date")]
        if dates:
            last_date = max(dates)

    return {
        "total_products": total_products,
        "total_categories": total_categories,
        "total_tickers": total_tickers,
        "price_records": len(prices),
        "util_records": len(utils),
        "last_crawl_date": last_date,
    }


@app.post("/chemical/crawl/start")
async def start_chemical_crawl(data: dict, background_tasks: BackgroundTasks):
    """启动化工数据爬取任务"""
    global chemical_crawl_status
    if chemical_crawl_status["status"] == "running":
        raise HTTPException(status_code=400, detail="爬取任务正在运行中")

    crawl_type = data.get("type", "all")
    chemical_crawl_status = {"status": "running", "progress": 0, "message": f"正在启动{crawl_type}爬取..."}

    def run_crawl():
        global chemical_crawl_status
        try:
            cmd = [sys.executable, os.path.join(BASE_DIR, "main.py")]
            if crawl_type == "price":
                cmd.append("--price-only")
            elif crawl_type == "utilization":
                cmd.append("--util-only")
            cmd.append("--no-import")

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0:
                chemical_crawl_status = {"status": "completed", "progress": 100, "message": "爬取完成"}
            else:
                chemical_crawl_status = {"status": "failed", "progress": 0, "message": proc.stderr[:200]}
        except Exception as e:
            chemical_crawl_status = {"status": "failed", "progress": 0, "message": str(e)[:200]}

    background_tasks.add_task(run_crawl)
    return {"message": "爬取任务已启动", "type": crawl_type}


@app.get("/chemical/crawl/status")
async def get_chemical_crawl_status():
    """获取化工爬取任务状态"""
    return chemical_crawl_status


@app.get("/chemical/export/prices")
async def export_chemical_prices():
    """导出化工价格 CSV"""
    path = os.path.join(CHEMICAL_OUTPUT_DIR, "chemical_prices.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="暂无价格数据")
    return FileResponse(path, filename="chemical_prices.csv", media_type="text/csv")


@app.get("/chemical/export/utilization")
async def export_chemical_utilization():
    """导出化工开工率 CSV"""
    path = os.path.join(CHEMICAL_OUTPUT_DIR, "chemical_utilization.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="暂无开工率数据")
    return FileResponse(path, filename="chemical_utilization.csv", media_type="text/csv")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_dir_exists": os.path.exists(DATA_DIR),
        "pdf_dir_exists": os.path.exists(PDF_DIR),
        "db_exists": os.path.exists(DB_PATH),
        "company_list_exists": os.path.exists(COMPANY_LIST_PATH),
    }

# ============== 启动入口 ==============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
