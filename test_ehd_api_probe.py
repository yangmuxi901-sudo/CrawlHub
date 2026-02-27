#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上证 e 互动 API 探测脚本
用于验证 e 互动平台的 API 可用性和返回数据格式

数据源：上证 e 互动 (sns.sseinfo.com)
"""

import requests
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://sns.sseinfo.com/",
    "Origin": "https://sns.sseinfo.com",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}


def test_ehd_api(stock_code, stock_name=""):
    """
    测试上证 e 互动 API

    Args:
        stock_code: 6 位股票代码（纯数字）
        stock_name: 股票名称（用于显示）
    """
    print(f"\n测试 e 互动：{stock_code} - {stock_name}")
    print("-" * 50)

    # e 互动 API 端点
    url = "https://sns.sseinfo.com/api/answer/list"

    # 请求参数
    params = {
        "stockcode": stock_code,
        "pageSize": "30",
        "pageNum": "1",
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
    }

    print(f"请求 URL: {url}")
    print(f"请求参数：stockcode={stock_code}")

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"状态码：{response.status_code}")

        if response.status_code != 200:
            print(f"❌ HTTP 错误：{response.status_code}")
            return None

        # 尝试解析 JSON
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ JSON 解析失败：{e}")
            print(f"响应内容：{response.text[:500]}")
            return None

        print(f"✅ 响应成功")

        # 检查返回数据结构
        print("\n返回数据结构:")
        for key in data.keys():
            value = data[key]
            if isinstance(value, list):
                print(f"  - {key}: 列表，共 {len(value)} 条")
            elif isinstance(value, dict):
                print(f"  - {key}: 对象")
            else:
                print(f"  - {key}: {value}")

        # 获取问答数据
        answers = data.get("data", []) or data.get("answers", []) or data.get("list", [])

        if not answers:
            # 尝试其他可能的字段
            for key in data.keys():
                if isinstance(data[key], list) and len(data[key]) > 0:
                    answers = data[key]
                    print(f"\n从字段 '{key}' 获取到数据")
                    break

        if answers:
            print(f"\n获取到 {len(answers)} 条问答记录")
            print("\n前 3 条记录详情：")
            for i, a in enumerate(answers[:3], 1):
                question_text = a.get("questionText", "") or a.get("question", "") or a.get("content", "")
                answer_text = a.get("answerText", "") or a.get("answer", "") or a.get("reply", "")
                timestamp = a.get("questionTime", 0) or a.get("askTime", 0) or a.get("create_time", 0)

                # 格式化时间
                if timestamp:
                    if isinstance(timestamp, (int, float)):
                        date_str = datetime.fromtimestamp(int(timestamp) / 1000).strftime("%Y-%m-%d")
                    else:
                        date_str = str(timestamp)[:10]
                else:
                    date_str = "未知"

                print(f"  [{i}] 日期：{date_str}")
                print(f"      提问：{question_text[:60]}...")
                print(f"      回复：{answer_text[:60] if answer_text else '无回复'}...")
                print()
        else:
            print("⚠️  无问答数据返回")

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


def test_ehd_attachment(attachment_url):
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
    """测试多只沪市股票"""

    # 测试用例：沪市代表性股票
    test_cases = [
        ("600071", "凤凰光学"),
        ("600000", "浦发银行"),
        ("600036", "招商银行"),
        ("601318", "中国平安"),
        ("688001", "华虹半导体"),
    ]

    print("=" * 60)
    print("上证 e 互动 API 探测")
    print("=" * 60)

    results = {"success": 0, "total": 0, "no_data": 0}

    for stock_code, name in test_cases:
        results["total"] += 1

        data = test_ehd_api(stock_code, name)

        if data:
            answers = data.get("data", []) or data.get("answers", []) or data.get("list", [])
            if answers:
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
        print(f"✅ e 互动 API 可用，{results['success']} 只股票有问答数据")
        print("   可以继续开发下载器脚本")
    else:
        print("❌ e 互动 API 可能已变更或需要特殊参数")
        print("   建议：")
        print("   1. 检查 API 端点是否正确")
        print("   2. 检查请求参数格式")
        print("   3. 可能需要在浏览器中登录后查看请求")
