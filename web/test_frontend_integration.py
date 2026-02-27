#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
前端集成测试 - 模拟前端操作测试后端 API
"""

import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

def print_section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def test_ui_page():
    """测试 UI 页面是否可访问"""
    print("\n[1] UI 页面测试")
    resp = requests.get(f"{API_BASE}/ui")
    passed = resp.status_code == 200 and "股东报告管理" in resp.text
    print(f"    状态码: {resp.status_code}")
    print(f"    包含标题: {'股东报告管理' in resp.text}")
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    return passed

def test_frontend_flow():
    """测试前端典型操作流程"""
    print_section("前端集成测试")

    all_passed = True

    # 1. 页面加载时获取统计数据
    print("\n[2] 页面加载 - 获取统计数据")
    resp = requests.get(f"{API_BASE}/stats/overview")
    data = resp.json()
    print(f"    公司总数: {data.get('total_companies')}")
    print(f"    PDF 总数: {data.get('total_pdfs')}")
    print(f"    有文件公司: {data.get('companies_with_files')}")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 2. 获取任务状态
    print("\n[3] 获取任务状态")
    resp = requests.get(f"{API_BASE}/task/status")
    data = resp.json()
    print(f"    状态: {data.get('status')}")
    print(f"    进度: {data.get('progress')}/{data.get('total')}")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 3. 获取公司列表（分页）
    print("\n[4] 获取公司列表")
    resp = requests.get(f"{API_BASE}/companies?page=1&page_size=10")
    data = resp.json()
    print(f"    总数: {data.get('total')}")
    print(f"    当前页: {len(data.get('items', []))} 条")
    if data.get('items'):
        print(f"    示例: {data['items'][0].get('ticker')} - {data['items'][0].get('company_name')}")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 4. 搜索公司
    print("\n[5] 搜索公司")
    resp = requests.get(f"{API_BASE}/companies?search=002&page_size=5")
    data = resp.json()
    print(f"    搜索 '002': 找到 {data.get('total')} 条")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 5. 按交易所筛选
    print("\n[6] 按交易所筛选")
    resp = requests.get(f"{API_BASE}/companies?exchange=sh&page_size=5")
    data = resp.json()
    print(f"    上海交易所: {data.get('total')} 家公司")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 6. 获取日志
    print("\n[7] 获取运行日志")
    resp = requests.get(f"{API_BASE}/logs?lines=5")
    data = resp.json()
    print(f"    总行数: {data.get('total')}")
    print(f"    返回: {data.get('returned')} 行")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 7. 浏览文件
    print("\n[8] 浏览文件")
    resp = requests.get(f"{API_BASE}/files/browse")
    data = resp.json()
    print(f"    文件夹数: {data.get('total', len(data.get('folders', [])))}")
    passed = resp.status_code == 200
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 8. 浏览特定公司文件
    print("\n[9] 浏览特定公司文件")
    # 获取一个有文件的公司
    stats_resp = requests.get(f"{API_BASE}/stats/companies?page=1&page_size=1")
    stats_data = stats_resp.json()
    if stats_data.get("items"):
        ticker = stats_data["items"][0]["ticker"]
        resp = requests.get(f"{API_BASE}/files/browse?ticker={ticker}")
        data = resp.json()
        print(f"    公司: {ticker}")
        print(f"    文件数: {data.get('count', 0)}")
        passed = resp.status_code == 200
    else:
        print("    没有有文件的公司")
        passed = True
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    # 9. 导出测试
    print("\n[10] CSV 导出")
    resp = requests.get(f"{API_BASE}/export/csv")
    passed = resp.status_code == 200 and "text/csv" in resp.headers.get("content-type", "")
    print(f"    状态码: {resp.status_code}")
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    print("\n[11] JSON 导出")
    resp = requests.get(f"{API_BASE}/export/json")
    data = resp.json()
    passed = resp.status_code == 200 and "overview" in data
    print(f"    状态码: {resp.status_code}")
    print(f"    包含概览: {'overview' in data}")
    print(f"    结果: {'✅ 通过' if passed else '❌ 失败'}")
    all_passed = all_passed and passed

    return all_passed

def test_api_performance():
    """测试 API 性能"""
    print_section("API 性能测试")

    import time

    tests = [
        ("统计数据", f"{API_BASE}/stats/overview"),
        ("公司列表", f"{API_BASE}/companies?page=1&page_size=20"),
        ("任务状态", f"{API_BASE}/task/status"),
        ("日志", f"{API_BASE}/logs?lines=100"),
        ("文件浏览", f"{API_BASE}/files/browse"),
    ]

    all_passed = True
    for name, url in tests:
        start = time.time()
        resp = requests.get(url)
        elapsed = (time.time() - start) * 1000  # ms
        passed = resp.status_code == 200 and elapsed < 2000  # 2秒内响应
        print(f"    {name}: {elapsed:.0f}ms {'✅' if passed else '❌'}")
        all_passed = all_passed and passed

    return all_passed

def main():
    print("\n" + "="*50)
    print("  股东报告管理 - 前端集成测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # 检查服务
    try:
        requests.get(f"{API_BASE}/health", timeout=2)
    except:
        print("\n❌ 错误: API 服务未启动")
        return

    # UI 测试
    ui_passed = test_ui_page()

    # 集成测试
    flow_passed = test_frontend_flow()

    # 性能测试
    perf_passed = test_api_performance()

    # 汇总
    print_section("测试汇总")
    print(f"    UI 页面测试: {'✅ 通过' if ui_passed else '❌ 失败'}")
    print(f"    前端流程测试: {'✅ 通过' if flow_passed else '❌ 失败'}")
    print(f"    API 性能测试: {'✅ 通过' if perf_passed else '❌ 失败'}")

    all_passed = ui_passed and flow_passed and perf_passed
    print(f"\n    总体结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")

    return all_passed

if __name__ == "__main__":
    main()
