#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
互动易 API 端点最终测试
基于已知信息和常见模式
"""

import requests
import time
from datetime import datetime

session = requests.Session()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://irm.cninfo.com.cn/",
}

# 可能的端点（基于搜索结果和常见模式）
ENDPOINTS = [
    # 基础端点
    "https://irm.cninfo.com.cn/ircs/hello",
    "https://irm.cninfo.com.cn/ircs/index",
    "https://irm.cninfo.com.cn/ircs/init",

    # 问答相关
    "https://irm.cninfo.com.cn/ircs/qa",
    "https://irm.cninfo.com.cn/ircs/qa/list",
    "https://irm.cninfo.com.cn/ircs/qa/query",

    # 公司相关
    "https://irm.cninfo.com.cn/ircs/company/list",
    "https://irm.cninfo.com.cn/ircs/company/query",

    # 搜索相关
    "https://irm.cninfo.com.cn/ircs/search",
    "https://irm.cninfo.com.cn/ircs/search/list",

    # 其他可能
    "https://irm.cninfo.com.cn/v1/ircs/question/list",
    "https://irm.cninfo.com.cn/api/v1/question/list",
]


def test_all_endpoints():
    """测试所有端点"""
    print("=" * 60)
    print("互动易 API 端点全面测试")
    print("=" * 60)

    # 先访问首页
    print("\n访问首页...")
    resp = session.get("https://irm.cninfo.com.cn/", headers=HEADERS, timeout=15)
    print(f"首页状态码：{resp.status_code}")

    # 测试参数
    params = {
        "stockcode": "300054",
        "pageSize": "30",
        "pageNum": "1",
        "beginDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
    }

    results = {"success": [], "failed": []}

    for endpoint in ENDPOINTS:
        print(f"\n测试：{endpoint}")

        # 尝试 GET
        try:
            resp = session.get(endpoint, headers=HEADERS, params=params, timeout=10)
            print(f"  GET: {resp.status_code}")

            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', '')
                if 'json' in content_type:
                    try:
                        data = resp.json()
                        print(f"  ✅ JSON! Keys: {list(data.keys())[:5]}")
                        results["success"].append((endpoint, "GET", data))
                    except:
                        print(f"  响应：{resp.text[:100]}")
                else:
                    print(f"  HTML/其他响应，长度：{len(resp.content)}")
        except Exception as e:
            print(f"  GET 异常：{e}")

        # 尝试 POST
        try:
            resp = session.post(endpoint, headers=HEADERS, data=params, timeout=10)
            print(f"  POST: {resp.status_code}")

            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', '')
                if 'json' in content_type:
                    try:
                        data = resp.json()
                        print(f"  ✅ JSON! Keys: {list(data.keys())[:5]}")
                        results["success"].append((endpoint, "POST", data))
                    except:
                        print(f"  响应：{resp.text[:100]}")
                else:
                    print(f"  HTML/其他响应，长度：{len(resp.content)}")
        except Exception as e:
            print(f"  POST 异常：{e}")

        time.sleep(0.5)

    return results


if __name__ == "__main__":
    results = test_all_endpoints()

    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    if results["success"]:
        print(f"\n✅ 找到 {len(results['success'])} 个可用端点:")
        for endpoint, method, data in results["success"]:
            print(f"  - {method} {endpoint}")
    else:
        print("\n❌ 未找到可用端点")
        print("\n结论：互动易平台可能需要：")
        print("  1. 登录后的 Session/Cookie")
        print("  2. 特殊的请求头（如 Token、签名）")
        print("  3. 浏览器环境（需要 Selenium/Playwright）")
