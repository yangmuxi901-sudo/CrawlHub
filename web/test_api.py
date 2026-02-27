#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股东报告管理 API 测试脚本
测试所有 API 端点
"""

import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime

# 配置
API_BASE = "http://localhost:8000"
TEST_RESULTS = []

def log_result(test_name: str, passed: bool, message: str = "", data: dict = None):
    """记录测试结果"""
    result = {
        "test": test_name,
        "passed": passed,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    TEST_RESULTS.append(result)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"      {message}")
    if data and not passed:
        print(f"      数据: {json.dumps(data, ensure_ascii=False)[:200]}")

def test_api_root():
    """测试 API 根路径"""
    try:
        resp = requests.get(f"{API_BASE}/", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "message" in data
        log_result("API 根路径", passed, f"状态码: {resp.status_code}", data)
        return passed
    except Exception as e:
        log_result("API 根路径", False, str(e))
        return False

def test_health_check():
    """测试健康检查"""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and data.get("status") == "healthy"
        log_result("健康检查", passed,
                   f"数据目录: {data.get('data_dir_exists')}, PDF目录: {data.get('pdf_dir_exists')}",
                   data)
        return passed
    except Exception as e:
        log_result("健康检查", False, str(e))
        return False

def test_stats_overview():
    """测试统计概览"""
    try:
        resp = requests.get(f"{API_BASE}/stats/overview", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "total_companies" in data
        log_result("统计概览", passed,
                   f"公司: {data.get('total_companies')}, PDF: {data.get('total_pdfs')}",
                   data)
        return passed, data
    except Exception as e:
        log_result("统计概览", False, str(e))
        return False, None

def test_companies_list():
    """测试公司列表"""
    try:
        resp = requests.get(f"{API_BASE}/companies?page=1&page_size=5", timeout=10)
        data = resp.json()
        passed = resp.status_code == 200 and "items" in data and "total" in data
        item_count = len(data.get("items", []))
        log_result("公司列表", passed,
                   f"总数: {data.get('total')}, 返回: {item_count} 条",
                   {"total": data.get("total"), "items_count": item_count})
        return passed
    except Exception as e:
        log_result("公司列表", False, str(e))
        return False

def test_companies_search():
    """测试公司搜索"""
    try:
        # 搜索 "平安"
        resp = requests.get(f"{API_BASE}/companies?search=平安&page_size=5", timeout=10)
        data = resp.json()
        passed = resp.status_code == 200 and "items" in data
        log_result("公司搜索 (平安)", passed,
                   f"找到: {data.get('total')} 条",
                   {"total": data.get("total")})
        return passed
    except Exception as e:
        log_result("公司搜索", False, str(e))
        return False

def test_companies_filter_exchange():
    """测试按交易所筛选"""
    try:
        resp = requests.get(f"{API_BASE}/companies?exchange=sz&page_size=5", timeout=10)
        data = resp.json()
        passed = resp.status_code == 200 and "items" in data

        # 验证返回的都是深交所
        all_sz = all(item.get("exchange") == "sz" for item in data.get("items", []))
        log_result("交易所筛选 (sz)", passed and all_sz,
                   f"深交所公司: {data.get('total')} 条")
        return passed and all_sz
    except Exception as e:
        log_result("交易所筛选", False, str(e))
        return False

def test_company_stats():
    """测试公司统计列表"""
    try:
        resp = requests.get(f"{API_BASE}/stats/companies?page=1&page_size=5&sort_by=count&order=desc", timeout=10)
        data = resp.json()
        passed = resp.status_code == 200 and "items" in data

        # 验证排序（降序）
        items = data.get("items", [])
        is_sorted = all(items[i]["pdf_count"] >= items[i+1]["pdf_count"]
                       for i in range(len(items)-1)) if len(items) > 1 else True

        log_result("公司统计列表", passed and is_sorted,
                   f"总数: {data.get('total')}, 排序正确: {is_sorted}")
        return passed
    except Exception as e:
        log_result("公司统计列表", False, str(e))
        return False

def test_file_distribution():
    """测试文件分布"""
    try:
        resp = requests.get(f"{API_BASE}/stats/distribution", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "distribution" in data
        dist = data.get("distribution", {})
        log_result("文件分布", passed,
                   f"分布类型: {len(dist)} 种")
        return passed
    except Exception as e:
        log_result("文件分布", False, str(e))
        return False

def test_task_status():
    """测试任务状态"""
    try:
        resp = requests.get(f"{API_BASE}/task/status", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "status" in data
        log_result("任务状态", passed,
                   f"状态: {data.get('status')}, 进度: {data.get('progress')}/{data.get('total')}")
        return passed
    except Exception as e:
        log_result("任务状态", False, str(e))
        return False

def test_logs():
    """测试日志获取"""
    try:
        resp = requests.get(f"{API_BASE}/logs?lines=10", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "logs" in data
        log_result("日志获取", passed,
                   f"总行数: {data.get('total')}, 返回: {data.get('returned')} 行")
        return passed
    except Exception as e:
        log_result("日志获取", False, str(e))
        return False

def test_database_records():
    """测试数据库记录"""
    try:
        resp = requests.get(f"{API_BASE}/database/records", timeout=10)
        data = resp.json()
        passed = resp.status_code == 200 and "records" in data
        log_result("数据库记录", passed,
                   f"记录数: {data.get('total')}")
        return passed
    except Exception as e:
        log_result("数据库记录", False, str(e))
        return False

def test_files_browse():
    """测试文件浏览"""
    try:
        resp = requests.get(f"{API_BASE}/files/browse", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "folders" in data
        log_result("文件浏览", passed,
                   f"文件夹数: {data.get('total', len(data.get('folders', [])))}")
        return passed
    except Exception as e:
        log_result("文件浏览", False, str(e))
        return False

def test_files_browse_company():
    """测试浏览特定公司文件"""
    try:
        # 先获取一个有文件的公司
        stats_resp = requests.get(f"{API_BASE}/stats/companies?page=1&page_size=1", timeout=5)
        stats_data = stats_resp.json()

        if not stats_data.get("items"):
            log_result("浏览公司文件", False, "没有有文件的公司")
            return False

        ticker = stats_data["items"][0]["ticker"]
        resp = requests.get(f"{API_BASE}/files/browse?ticker={ticker}", timeout=5)
        data = resp.json()
        passed = resp.status_code == 200 and "files" in data
        log_result("浏览公司文件", passed,
                   f"公司: {ticker}, 文件数: {data.get('count', 0)}")
        return passed
    except Exception as e:
        log_result("浏览公司文件", False, str(e))
        return False

def test_export_csv():
    """测试 CSV 导出"""
    try:
        resp = requests.get(f"{API_BASE}/export/csv", timeout=10)
        passed = resp.status_code == 200 and "text/csv" in resp.headers.get("content-type", "")
        log_result("CSV 导出", passed,
                   f"内容类型: {resp.headers.get('content-type', 'N/A')[:50]}")
        return passed
    except Exception as e:
        log_result("CSV 导出", False, str(e))
        return False

def test_export_json():
    """测试 JSON 导出"""
    try:
        resp = requests.get(f"{API_BASE}/export/json", timeout=10)
        passed = resp.status_code == 200

        if passed:
            data = resp.json()
            passed = "overview" in data and "companies" in data

        log_result("JSON 导出", passed,
                   f"状态码: {resp.status_code}")
        return passed
    except Exception as e:
        log_result("JSON 导出", False, str(e))
        return False

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("股东报告管理 API 测试")
    print("=" * 60)
    print()

    # 基础测试
    print("--- 基础测试 ---")
    test_api_root()
    test_health_check()

    # 统计测试
    print("\n--- 统计测试 ---")
    test_stats_overview()
    test_company_stats()
    test_file_distribution()

    # 公司测试
    print("\n--- 公司测试 ---")
    test_companies_list()
    test_companies_search()
    test_companies_filter_exchange()

    # 任务测试
    print("\n--- 任务测试 ---")
    test_task_status()

    # 日志测试
    print("\n--- 日志测试 ---")
    test_logs()

    # 数据库测试
    print("\n--- 数据库测试 ---")
    test_database_records()

    # 文件测试
    print("\n--- 文件测试 ---")
    test_files_browse()
    test_files_browse_company()

    # 导出测试
    print("\n--- 导出测试 ---")
    test_export_csv()
    test_export_json()

    # 汇总
    print("\n" + "=" * 60)
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = sum(1 for r in TEST_RESULTS if not r["passed"])
    total = len(TEST_RESULTS)

    print(f"测试结果: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        print("\n失败的测试:")
        for r in TEST_RESULTS:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['message']}")

    return failed == 0

if __name__ == "__main__":
    # 检查 API 是否可访问
    try:
        requests.get(f"{API_BASE}/health", timeout=2)
    except:
        print("错误: API 服务未启动")
        print("请先运行: python3 api.py")
        sys.exit(1)

    success = run_all_tests()
    sys.exit(0 if success else 1)
