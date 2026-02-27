#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CSV 导出模块
将爬取的化工数据导出为标准 CSV 格式
- 编码: UTF-8
- 日期格式: YYYY-MM-DD
- 数值: 保留2位小数
"""

import os
import pandas as pd
from datetime import datetime


def export_prices_csv(df, output_dir, with_date_suffix=True):
    """
    导出价格数据 CSV
    参数:
        df: 价格 DataFrame
        output_dir: 输出目录
        with_date_suffix: 是否带日期后缀
    返回: 输出文件路径
    """
    if df is None or df.empty:
        return None

    os.makedirs(output_dir, exist_ok=True)

    # 数值保留2位小数
    for col in ["price", "price_change"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    # 日期格式标准化
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    paths = []

    # 带日期后缀版本
    if with_date_suffix:
        today_str = datetime.now().strftime("%Y%m%d")
        path = os.path.join(output_dir, f"chemical_prices_{today_str}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        paths.append(path)

    # 最新版本（不带日期）
    latest_path = os.path.join(output_dir, "chemical_prices.csv")
    df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    paths.append(latest_path)

    return paths


def export_utilization_csv(df, output_dir, with_date_suffix=True):
    """
    导出开工率数据 CSV
    """
    if df is None or df.empty:
        return None

    os.makedirs(output_dir, exist_ok=True)

    for col in ["utilization_rate", "week_change"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    if "stat_date" in df.columns:
        df["stat_date"] = pd.to_datetime(df["stat_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    paths = []

    if with_date_suffix:
        today_str = datetime.now().strftime("%Y%m%d")
        path = os.path.join(output_dir, f"chemical_utilization_{today_str}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        paths.append(path)

    latest_path = os.path.join(output_dir, "chemical_utilization.csv")
    df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    paths.append(latest_path)

    return paths
