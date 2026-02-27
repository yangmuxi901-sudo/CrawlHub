#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股投资者关系 API 探测脚本 v2
测试多个可能的数据源
"""

import requests
import time
import json
from datetime import datetime
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def test_cninfo_v2(stock_code, market):
    """测试巨潮资讯 - 使用完整股票代码格式"""
    print(f"\n[巨潮资讯] {stock_code} ({market})")
    print("-" * 40)

    # 完整股票代码格式
    if market == "sh":
        full_code = f"SH{stock_code}"
        column = "sse"
    elif market == "sz":
        full_code = f"SZ{stock_code}"
        column = "szse"
    elif market == "bj":
        full_code = f"BJ{stock_code}"
        column = "bjse"
    else:
        full_code = stock_code
        column = "szse"

    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    params = {
        "currentPage": "1",
        "pageSize": "30",
        "column": column,
        "searchkey": quote("投资者关系活动记录".encode("utf-8")),
        "secCode": full_code,
        "secMarket": column,
        "plate": "",
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "sortName": "time",
        "sortType": "desc",
    }

    try:
        resp = requests.post(url, headers=HEADERS, data=params, timeout=15)
        print(f"状态码：{resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("announcements"):
                print(f"返回公告数：{len(data['announcements'])}")
                # 显示第一条
                first = data["announcements"][0]
                print(f"示例：{first.get('title', 'N/A')}")
                return True
            else:
                print("无数据")
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


def test_szse_api(stock_code):
    """
    测试深交所 API
    http://www.szse.cn/api/report/ShowReport/data
    """
    print(f"\n[深交所 API] {stock_code}")
    print("-" * 40)

    # 深交所投资者关系记录 API
    url = "http://www.szse.cn/api/report/ShowReport/data"

    params = {
        "REPORTNAME": "ERPInvestorRelaManageRecord",
        "COLUMNID": "0",
        "SHOWTYPE": "JSON",
        "CATALOGID": "1279",
        "TABKEY": "tab1",
        "PAGENO": "1",
        "PAGESIZE": "20",
        "random": str(time.time()),
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"状态码：{resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"返回数据：{json.dumps(data, ensure_ascii=False)[:500]}")
            return True
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


def test_sse_api(stock_code):
    """
    测试上交所 API
    """
    print(f"\n[上交所 API] {stock_code}")
    print("-" * 40)

    # 上交所公告查询 API
    url = "http://www.sse.com.cn/assistant/bridge/api/ann/bulletin"

    params = {
        "sqlId": "0",
        "comId": stock_code,
        "pageHelp.pageSize": "20",
        "pageHelp.pageNo": "1",
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"状态码：{resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"返回数据：{json.dumps(data, ensure_ascii=False)[:500]}")
            return True
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


def test_cninfo_general(keyword="投资者关系"):
    """
    测试巨潮资讯通用搜索（不指定股票代码）
    """
    print(f"\n[巨潮资讯 - 通用搜索] 关键词：{keyword}")
    print("-" * 40)

    url = "http://www.cninfo.com.cn/new/fulltextSearch"

    params = {
        "notautosubmit": "false",
        "keyWord": quote(keyword.encode("utf-8")),
        "stock": "",
        "xsbq": "full",
        "category": "",
        "pd": "2024-01-01",
        "ed": datetime.now().strftime("%Y-%m-%d"),
        "currentPage": "1",
        "pageSize": "10",
        "fixedFilter": "",
    }

    try:
        resp = requests.post(url, headers=HEADERS, data=params, timeout=15)
        print(f"状态码：{resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"响应：{json.dumps(data, ensure_ascii=False)[:800]}")
            return True
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


def test_akshare():
    """测试 akshare 库"""
    print(f"\n[akshare] 测试")
    print("-" * 40)

    try:
        import akshare as ak

        # 尝试获取投资者关系记录
        # stock_ir_proposed_df = ak.stock_ir_proposed()
        # print(ak.stock_ir_proposed.__doc__)

        print("akshare 已安装")

        # 列出相关的函数
        funcs = [f for f in dir(ak) if "ir" in f.lower() or "investor" in f.lower()]
        if funcs:
            print(f"相关函数：{funcs}")

        return True
    except ImportError:
        print("akshare 未安装")
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


def test_simple_cninfo(stock_code, market):
    """
    简化版巨潮测试 - 不带复杂参数
    """
    print(f"\n[巨潮 - 简化版] {stock_code} ({market})")
    print("-" * 40)

    # 参考网上实际的 API 调用格式
    url = "http://www.cninfo.com.cn/new/fulltextSearch/full"

    # 构造 stock 参数格式：SZ300054
    stock_param = f"{market.upper()}{stock_code}"

    data = {
        "secmgr": "",
        "keyWord": "投资者关系活动记录表",
        "stock": stock_param,
        "xsbq": "full",
        "category": "",
        "pd": "2024-01-01",
        "ed": datetime.now().strftime("%Y-%m-%d"),
        "currentPage": "1",
        "pageSize": "20",
        "fixedFilter": "",
    }

    headers = dict(HEADERS)
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    try:
        resp = requests.post(url, headers=headers, data=data, timeout=15)
        print(f"状态码：{resp.status_code}")

        if resp.status_code == 200:
            result = resp.json()
            if "announcement" in result:
                anns = result["announcement"]
                print(f"返回公告数：{len(anns)}")
                if anns:
                    print(f"第一条：{anns[0].get('title', 'N/A')[:50]}")
                    print(f"PDF URL: http://static.cninfo.com.cn/{anns[0].get('adjunctUrl', '')}")
            else:
                print(f"响应：{json.dumps(result, ensure_ascii=False)[:500]}")
            return True
        return False
    except Exception as e:
        print(f"错误：{e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("A 股投资者关系 API 探测脚本 v2")
    print("=" * 60)

    # 测试用例
    test_stocks = [
        ("300054", "sz", "鼎龙股份"),
        ("600071", "sh", "凤凰光学"),
        ("920001", "bj", "纬达光电"),
    ]

    print("\n=== 测试 1: 巨潮资讯简化版 API ===")
    for code, market, name in test_stocks:
        test_simple_cninfo(code, market)
        time.sleep(2)

    print("\n=== 测试 2: akshare ===")
    test_akshare()

    print("\n=== 测试 3: 巨潮通用搜索 ===")
    test_cninfo_general("投资者关系活动记录表")
