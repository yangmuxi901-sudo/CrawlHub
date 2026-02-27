#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
双平台 API 综合探测脚本
探测互动易和 e 互动的真实 API 端点
"""

import requests
import time
from datetime import datetime

# 请求头
HDY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://irm.cninfo.com.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

EHD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://sns.sseinfo.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 互动易可能的端点
HDY_ENDPOINTS = [
    "https://irm.cninfo.com.cn/ircs/q.do",
    "https://irm.cninfo.com.cn/ircs/question/list.do",
    "https://irm.cninfo.com.cn/ircs/question/query.do",
    "https://irm.cninfo.com.cn/question/list",
    "https://irm.cninfo.com.cn/new/ircs/question/list",
]

# e 互动可能的端点 (基于找到的 ajax/feeds.do 等)
EHD_ENDPOINTS = [
    "https://sns.sseinfo.com/ajax/feeds.do",
    "https://sns.sseinfo.com/ajax/ques/list.do",
    "https://sns.sseinfo.com/latesteasytalk.do",
    "https://sns.sseinfo.com/irelate/list.do",
    "https://sns.sseinfo.com/question/list.do",
    "https://sns.sseinfo.com/answer/list.do",
]


def test_hdy_endpoints(stock_code="300054"):
    """测试互动易端点"""
    print("\n" + "=" * 60)
    print("深交所互动易 API 端点探测")
    print("=" * 60)

    params = {
        "stockcode": stock_code,
        "pageSize": "30",
        "pageNum": "1",
    }

    for endpoint in HDY_ENDPOINTS:
        print(f"\n测试：{endpoint}")
        try:
            response = requests.post(endpoint, headers=HDY_HEADERS, data=params, timeout=15)
            print(f"  状态码：{response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  ✅ JSON 响应！Keys: {list(data.keys())[:5]}")
                    return endpoint, data
                except:
                    print(f"  非 JSON 响应，长度：{len(response.text)}")
                    return endpoint, response.text[:500]
            else:
                print(f"  ❌ 错误：{response.status_code}")
        except Exception as e:
            print(f"  ❌ 异常：{e}")

        time.sleep(1)

    return None, None


def test_ehd_endpoints(stock_code="600071"):
    """测试 e 互动端点"""
    print("\n" + "=" * 60)
    print("上证 e 互动 API 端点探测")
    print("=" * 60)

    params = {
        "stockcode": stock_code,
        "pageSize": "30",
        "pageNum": "1",
        "type": " ques",
    }

    for endpoint in EHD_ENDPOINTS:
        print(f"\n测试：{endpoint}")
        try:
            response = requests.post(endpoint, headers=EHD_HEADERS, data=params, timeout=15)
            print(f"  状态码：{response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  ✅ JSON 响应！Keys: {list(data.keys())[:5]}")
                    return endpoint, data
                except:
                    print(f"  非 JSON 响应，长度：{len(response.text)}")
                    return endpoint, response.text[:500]
            else:
                print(f"  ❌ 错误：{response.status_code}")
        except Exception as e:
            print(f"  ❌ 异常：{e}")

        time.sleep(1)

    return None, None


if __name__ == "__main__":
    print("=" * 60)
    print("双平台 API 端点综合探测")
    print("=" * 60)

    # 测试互动易
    hdy_endpoint, hdy_data = test_hdy_endpoints()

    # 测试 e 互动
    ehd_endpoint, ehd_data = test_ehd_endpoints()

    # 输出结果
    print("\n" + "=" * 60)
    print("探测结果汇总")
    print("=" * 60)

    if hdy_endpoint:
        print(f"\n✅ 互动易找到可用端点：{hdy_endpoint}")
        print(f"   返回数据：{str(hdy_data)[:200]}")
    else:
        print("\n❌ 互动易：未找到可用端点")

    if ehd_endpoint:
        print(f"\n✅ e 互动找到可用端点：{ehd_endpoint}")
        print(f"   返回数据：{str(ehd_data)[:200]}")
    else:
        print("\n❌ e 互动：未找到可用端点")
