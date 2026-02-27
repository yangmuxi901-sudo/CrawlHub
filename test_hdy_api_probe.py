#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深交所互动易 API 探测脚本 - 多端点测试
用于验证互动易平台的 API 可用性和返回数据格式

数据源：深交所互动易 (irm.cninfo.com.cn)
"""

import requests
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://irm.cninfo.com.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}

# 可能的 API 端点列表
API_ENDPOINTS = [
    "http://irm.cninfo.com.cn/ircs/question/list",
    "http://irm.cninfo.com.cn/ircs/question/query",
    "http://irm.cninfo.com.cn/api/question/list",
    "http://irm.cninfo.com.cn/new/ircs/question/list",
    "https://irm.cninfo.com.cn/ircs/question/list",
]


def test_hdy_api(stock_code, stock_name=""):
    """
    测试深交所互动易 API - 多端点测试

    Args:
        stock_code: 6 位股票代码（纯数字）
        stock_name: 股票名称（用于显示）
    """
    print(f"\n测试互动易：{stock_code} - {stock_name}")
    print("-" * 50)

    params = {
        "stockcode": stock_code,
        "orgId": "",
        "pageSize": "30",
        "pageNum": "1",
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
    }

    for endpoint in API_ENDPOINTS:
        print(f"\n尝试端点：{endpoint}")
        try:
            response = requests.post(endpoint, headers=HEADERS, data=params, timeout=15)
            print(f"  状态码：{response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  ✅ 成功！返回数据结构：{list(data.keys())}")
                    questions = data.get("data", []) or data.get("questions", []) or data.get("list", [])
                    if questions:
                        print(f"  获取到 {len(questions)} 条问答")
                        return endpoint, data
                    else:
                        print("  ⚠️  无数据返回")
                except Exception as e:
                    print(f"  JSON 解析失败：{e}")
            elif response.status_code == 405:
                print("  ❌ 方法不允许 (405)")
            elif response.status_code == 404:
                print("  ❌ 未找到 (404)")
            else:
                print(f"  ❌ 错误：{response.status_code}")
        except requests.exceptions.Timeout:
            print("  ❌ 超时")
        except Exception as e:
            print(f"  ❌ 错误：{e}")

        time.sleep(1)

    return None, None


def test_hdy_attachment(attachment_url):
    """
    测试附件下载链接

    Args:
        attachment_url: 附件 URL
    """
    print(f"\n测试附件下载：{attachment_url[:80]}...")

    try:
        response = requests.get(attachment_url, headers=HEADERS, timeout=15, stream=True)
        print(f"状态码：{response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")

        content_length = response.headers.get('Content-Length', 'unknown')
        print(f"文件大小：{content_length} bytes")

        if response.status_code == 200:
            print("✅ 附件下载链接有效")
            return True
        else:
            print(f"❌ 附件下载失败：{response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 下载错误：{e}")
        return False


def test_multiple_stocks():
    """测试多只深市股票"""

    # 测试用例：深市代表性股票
    test_cases = [
        ("300054", "鼎龙股份"),
        ("300866", "安克创新"),
        ("000020", "深华发 A"),
        ("002415", "海康威视"),
        ("300750", "宁德时代"),
    ]

    print("=" * 60)
    print("深交所互动易 API 探测")
    print("=" * 60)

    results = {"success": 0, "total": 0, "no_data": 0}

    for stock_code, name in test_cases:
        results["total"] += 1

        data = test_hdy_api(stock_code, name)

        if data:
            questions = data.get("data", []) or data.get("questions", []) or data.get("list", [])
            if questions:
                results["success"] += 1
            else:
                results["no_data"] += 1

        # 反爬休眠
        time.sleep(2)

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"测试股票数：{results['total']}")
    print(f"有数据：{results['success']}")
    print(f"无数据：{results['no_data']}")

    return results


if __name__ == "__main__":
    # 运行测试
    results = test_multiple_stocks()

    # 根据结果给出建议
    print("\n" + "=" * 60)
    print("分析建议")
    print("=" * 60)

    if results["success"] > 0:
        print(f"✅ 互动易 API 可用，{results['success']} 只股票有问答数据")
        print("   可以继续开发下载器脚本")
    else:
        print("❌ 互动易 API 可能已变更或需要特殊参数")
        print("   建议：")
        print("   1. 检查 API 端点是否正确")
        print("   2. 检查请求参数格式")
        print("   3. 可能需要在浏览器中登录后查看请求")
