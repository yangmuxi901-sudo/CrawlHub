#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
双平台 API 深度探测脚本
测试带 Cookie 和完整请求头的 API 调用
"""

import requests
import time
from datetime import datetime

# 先访问首页获取 Cookie
session = requests.Session()

HDY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

EHD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://sns.sseinfo.com",
}


def test_hdy_with_session():
    """测试互动易 - 带 Session"""
    print("\n" + "=" * 60)
    print("深交所互动易 - 带 Session 测试")
    print("=" * 60)

    # 先访问首页获取 Cookie
    print("访问首页获取 Cookie...")
    try:
        resp = session.get("https://irm.cninfo.com.cn/", headers=HDY_HEADERS, timeout=15)
        print(f"首页状态码：{resp.status_code}")
        print(f"Cookie: {session.cookies}")
    except Exception as e:
        print(f"首页访问失败：{e}")
        return

    # 尝试不同的参数格式
    test_cases = [
        # 端点，参数格式
        ("https://irm.cninfo.com.cn/ircs/q.do", {"stockcode": "300054", "pageSize": "30", "pageNum": "1"}),
        ("https://irm.cninfo.com.cn/ircs/question/list", {"stockcode": "300054", "pageSize": "30", "pageNum": "1"}),
    ]

    for endpoint, params in test_cases:
        print(f"\n测试：{endpoint}")
        print(f"参数：{params}")

        try:
            # POST 请求
            response = session.post(endpoint, headers=HDY_HEADERS, data=params, timeout=15)
            print(f"POST 状态码：{response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ JSON 响应！Keys: {list(data.keys())[:5]}")
                    return endpoint, data
                except:
                    print(f"响应内容：{response.text[:200]}")
            else:
                print(f"POST 失败：{response.status_code}")
        except Exception as e:
            print(f"POST 异常：{e}")

        try:
            # GET 请求
            response = session.get(endpoint, headers=HDY_HEADERS, params=params, timeout=15)
            print(f"GET 状态码：{response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ JSON 响应！Keys: {list(data.keys())[:5]}")
                    return endpoint, data
                except:
                    print(f"响应内容：{response.text[:200]}")
            else:
                print(f"GET 失败：{response.status_code}")
        except Exception as e:
            print(f"GET 异常：{e}")

        time.sleep(2)

    return None, None


def test_ehd_with_session():
    """测试 e 互动 - 带 Session"""
    print("\n" + "=" * 60)
    print("上证 e 互动 - 带 Session 测试")
    print("=" * 60)

    # 新建 Session
    session_ehd = requests.Session()

    # 先访问首页获取 Cookie
    print("访问首页获取 Cookie...")
    try:
        resp = session_ehd.get("https://sns.sseinfo.com/", headers=EHD_HEADERS, timeout=15)
        print(f"首页状态码：{resp.status_code}")
    except Exception as e:
        print(f"首页访问失败：{e}")
        return

    # e 互动可能的 API 端点
    test_cases = [
        ("https://sns.sseinfo.com/ajax/feeds.do", {"type": "ques", "stockcode": "600071"}),
        ("https://sns.sseinfo.com/latesteasytalk.do", {"stockcode": "600071"}),
    ]

    for endpoint, params in test_cases:
        print(f"\n测试：{endpoint}")
        print(f"参数：{params}")

        try:
            response = session_ehd.post(endpoint, headers=EHD_HEADERS, data=params, timeout=15)
            print(f"POST 状态码：{response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ JSON 响应！Keys: {list(data.keys())[:5]}")
                    return endpoint, data
                except:
                    print(f"响应内容：{response.text[:200]}")
            else:
                print(f"POST 失败：{response.status_code}")
        except Exception as e:
            print(f"POST 异常：{e}")

        time.sleep(2)

    return None, None


if __name__ == "__main__":
    print("=" * 60)
    print("双平台 API 深度探测 - 带 Session/Cookie")
    print("=" * 60)

    # 测试互动易
    hdy_endpoint, hdy_data = test_hdy_with_session()

    # 测试 e 互动
    ehd_endpoint, ehd_data = test_ehd_with_session()

    # 输出结果
    print("\n" + "=" * 60)
    print("探测结果汇总")
    print("=" * 60)

    if hdy_endpoint:
        print(f"\n✅ 互动易找到可用端点：{hdy_endpoint}")
    else:
        print("\n❌ 互动易：未找到可用端点 - 可能需要登录")

    if ehd_endpoint:
        print(f"\n✅ e 互动找到可用端点：{ehd_endpoint}")
    else:
        print("\n❌ e 互动：未找到可用端点 - 可能需要登录")

    print("\n" + "=" * 60)
    print("建议：两个平台可能都需要登录后才能访问 API")
    print("方案 1: 使用 Selenium/Playwright 模拟浏览器登录")
    print("方案 2: 使用第三方数据源 (如 Tushare、AkShare)")
    print("=" * 60)
