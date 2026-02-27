#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
隆众资讯页面解析器
解析价格行情和开工率数据
"""

import re
from bs4 import BeautifulSoup


def parse_price_table(html_content, product_name=""):
    """
    解析隆众资讯价格行情表格
    返回: list[dict] 每行一条价格记录
    """
    results = []
    if not html_content:
        return results

    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # 提取表头
        headers = []
        header_row = rows[0]
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

        if not headers:
            continue

        # 解析数据行
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            record = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    record[headers[i]] = cell.get_text(strip=True)

            # 尝试提取价格字段
            record = _normalize_price_record(record, product_name)
            if record:
                results.append(record)

    return results

def _normalize_price_record(record, product_name=""):
    """
    将原始表格记录标准化为统一字段
    尝试从各种可能的列名中提取价格、涨跌幅、地区等
    """
    if not record:
        return None

    # 价格字段候选
    price_keys = ["价格", "均价", "市场价", "出厂价", "报价", "中间价", "现金流"]
    price = _extract_float(record, price_keys)

    # 涨跌幅字段候选
    change_keys = ["涨跌", "涨跌幅", "较前日", "变动", "日涨跌"]
    price_change = _extract_float(record, change_keys)

    # 地区字段候选
    region_keys = ["地区", "区域", "市场", "产地"]
    region = _extract_text(record, region_keys) or "华东"

    # 单位字段候选
    unit_keys = ["单位", "计量单位"]
    unit = _extract_text(record, unit_keys) or "元/吨"

    if price is not None:
        return {
            "product_name": product_name,
            "price": round(price, 2),
            "price_change": round(price_change, 2) if price_change is not None else 0.0,
            "unit": unit,
            "region": region,
        }
    return None


def _extract_float(record, candidate_keys):
    """从记录中按候选键名提取浮点数"""
    for key in candidate_keys:
        for rk, rv in record.items():
            if key in rk:
                val = re.sub(r"[^\d.\-]", "", str(rv))
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
    return None


def _extract_text(record, candidate_keys):
    """从记录中按候选键名提取文本"""
    for key in candidate_keys:
        for rk, rv in record.items():
            if key in rk:
                text = str(rv).strip()
                if text:
                    return text
    return None

def parse_utilization_table(html_content, product_name=""):
    """
    解析隆众资讯开工率表格
    返回: list[dict] 每行一条开工率记录
    """
    results = []
    if not html_content:
        return results

    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = []
        header_row = rows[0]
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            record = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    record[headers[i]] = cell.get_text(strip=True)

            record = _normalize_utilization_record(record, product_name)
            if record:
                results.append(record)

    return results


def _normalize_utilization_record(record, product_name=""):
    """标准化开工率记录"""
    if not record:
        return None

    rate_keys = ["开工率", "负荷率", "产能利用率", "装置开工"]
    rate = _extract_float(record, rate_keys)

    change_keys = ["环比", "周环比", "变化", "较上周"]
    week_change = _extract_float(record, change_keys)

    if rate is not None:
        return {
            "product_name": product_name,
            "utilization_rate": round(rate, 2),
            "week_change": round(week_change, 2) if week_change is not None else 0.0,
        }
    return None


def parse_json_price_data(json_data, product_name=""):
    """
    解析 JSON 格式的价格数据（部分 API 返回 JSON）
    """
    results = []
    if not json_data:
        return results

    # 适配常见 JSON 结构
    data_list = json_data if isinstance(json_data, list) else json_data.get("data", [])

    for item in data_list:
        price = None
        for key in ["price", "avgPrice", "middlePrice", "value"]:
            if key in item:
                try:
                    price = float(item[key])
                    break
                except (ValueError, TypeError):
                    continue

        if price is not None:
            results.append({
                "product_name": product_name,
                "price": round(price, 2),
                "price_change": round(float(item.get("change", 0)), 2),
                "unit": item.get("unit", "元/吨"),
                "region": item.get("region", "华东"),
            })

    return results
