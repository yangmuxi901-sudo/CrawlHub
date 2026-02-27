#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
巨潮资讯网 API 探测脚本
用于验证不同交易所股票的 API 可用性和返回数据格式
"""

import requests
import time
from datetime import datetime
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://www.cninfo.com.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def test_cninfo_api(stock_code, market_type, stock_name=""):
    """
    测试巨潮资讯网 API

    Args:
        stock_code: 纯数字股票代码
        market_type: 市场类型 (sz/sh/bj)
        stock_name: 股票名称（用于显示）
    """
    print(f"\n测试：{stock_code} ({market_type}) - {stock_name}")
    print("-" * 50)

    # 巨潮 API 需要完整的证券市场代码格式
    # SZ: 00xxxx, 20xxxx, 30xxxx
    # SH: 60xxxx, 68xxxx
    # 需要添加市场前缀
    full_code = f"{market_type}{stock_code}" if not stock_code.startswith(market_type) else stock_code

    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    # 尝试不同的参数组合
    params = {
        "currentPage": "1",
        "pageSize": "30",
        "column": "szse",  # 深交所
        "searchkey": quote("投资者关系".encode("utf-8")),
        "secCode": stock_code,
        "secMarket": market_type,
        "plate": "",
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "sortName": "time",
        "sortType": "desc",
        "isHLtip": "",
    }

    # 打印实际请求参数便于调试
    print(f"请求参数：secCode={stock_code}, secMarket={market_type}")

    try:
        response = requests.post(url, headers=HEADERS, data=params, timeout=15)
        print(f"状态码：{response.status_code}")

        if response.status_code != 200:
            print(f"❌ HTTP 错误：{response.status_code}")
            return None

        data = response.json()

        # 检查是否有公告数据
        if "announcements" not in data or data["announcements"] is None:
            print("❌ 无公告数据返回")
            return None

        announcements = data["announcements"]
        print(f"返回公告数量：{len(announcements)}")

        # 过滤投资者关系相关记录
        ir_records = []
        for ann in announcements:
            title = ann.get("title", "")
            if "投资者关系" in title or "投资者调研" in title or "调研" in title:
                ir_records.append(ann)

        print(f"投资者相关记录：{len(ir_records)} 条")

        if ir_records:
            print("\n前 3 条记录详情：")
            for i, rec in enumerate(ir_records[:3], 1):
                print(f"  [{i}] {rec.get('title', '')}")
                print(f"      公告时间：{rec.get('announcementTime', '')}")
                print(f"      附件 URL: {rec.get('adjunctUrl', '')}")
                print(f"      公告类型：{rec.get('announcementType', '')}")
                print()

        return data

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求错误：{e}")
        return None
    except Exception as e:
        print(f"❌ 未知错误：{e}")
        return None


def test_different_markets():
    """测试不同交易所的股票"""

    # 测试用例：来自公司列表的代表性股票
    test_cases = [
        # 深交所 (sz) - 应该正常
        ("000020", "sz", "深华发 A"),
        ("300054", "sz", "鼎龙股份"),
        ("300866", "sz", "安克创新"),

        # 上交所 (sh) - 待验证
        ("600071", "sh", "凤凰光学"),
        ("600130", "sh", "*ST 波导"),

        # 北交所 (bj) - 待验证
        ("920001", "bj", "纬达光电"),
        ("920128", "bj", "华岭股份"),
    ]

    print("=" * 60)
    print("巨潮资讯网 API 探测 - 不同交易所测试")
    print("=" * 60)

    results = {
        "sz": {"success": 0, "total": 0},
        "sh": {"success": 0, "total": 0},
        "bj": {"success": 0, "total": 0},
    }

    for stock_code, market, name in test_cases:
        results[market]["total"] += 1

        data = test_cninfo_api(stock_code, market, name)

        if data and data.get("announcements"):
            results[market]["success"] += 1

        # 反爬休眠
        time.sleep(2)

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for market in ["sz", "sh", "bj"]:
        success = results[market]["success"]
        total = results[market]["total"]
        status = "✅" if success > 0 else "❌"
        print(f"{status} {market} 交易所：{success}/{total} 有数据")

    return results


def test_pdf_download(pdf_url):
    """
    测试 PDF 下载链接是否有效

    Args:
        pdf_url: PDF 完整 URL
    """
    print(f"\n测试 PDF 下载：{pdf_url[:80]}...")

    try:
        response = requests.get(pdf_url, headers=HEADERS, timeout=15, stream=True)
        print(f"状态码：{response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        print(f"文件大小：{len(response.content)} bytes")

        if response.status_code == 200:
            print("✅ PDF 下载链接有效")
            return True
        else:
            print(f"❌ PDF 下载失败：{response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 下载错误：{e}")
        return False


if __name__ == "__main__":
    # 运行测试
    results = test_different_markets()

    # 根据结果给出建议
    print("\n" + "=" * 60)
    print("建议")
    print("=" * 60)

    if results["sh"]["success"] == 0:
        print("⚠️  上交所股票在巨潮资讯网无数据")
        print("   建议：上交所股票需要寻找其他数据源（如上交所官网 API）")

    if results["bj"]["success"] == 0:
        print("⚠️  北交所股票在巨潮资讯网无数据")
        print("   建议：北交所股票需要寻找其他数据源")

    if results["sz"]["success"] > 0:
        print("✅ 深交所股票可以使用巨潮资讯网 API")
