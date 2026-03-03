#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
隆众资讯化工开工率爬虫 - 组合指标法
通过景气度指数估算开工率

数据源:
  1. 同花顺行业指数（AkShare）
  2. 期货库存数据（AkShare）
  3. 期货价格数据（AkShare）
  4. 宏观 PMI 数据（AkShare）

计算方法:
  景气度 = (行业指数分位数 + PMI - 库存分位数) / 3
  开工率 = 50% + 景气度 * 0.45 (50%-95% 范围)
"""

import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import (
    BaseCrawler, OUTPUT_DIR, load_products_config,
    get_last_crawl_date, update_crawl_date
)
from crawlers.prosperity_index_crawler import ProsperityIndexCrawler


class OilchemUtilizationCrawler(BaseCrawler):
    """化工开工率爬虫 - 组合指标法"""

    def __init__(self):
        super().__init__(name="OilchemUtilization")
        self.util_products = self.config.get("utilization_products", [])
        self.all_products = self.config.get("products", [])
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.prosperity_crawler = ProsperityIndexCrawler()

    def crawl(self):
        """爬取开工率数据 - 使用景气度指数估算"""
        all_records = []

        self.logger.log(f"待爬取开工率产品数：{len(self.util_products)}")
        self.logger.log("数据源：组合指标法（行业指数 + 期货库存 +PMI）")

        # 1. 计算整体景气度指数
        self.logger.log("计算化工行业整体景气度指数...")
        prosperity = self.prosperity_crawler.compute_prosperity_index()
        self.logger.log(f"整体景气度：{prosperity['overall_index']}")
        self.logger.log(f"  - 行业指数分项：{prosperity['industry_index']}")
        self.logger.log(f"  - 库存分项：{prosperity['inventory_index']}")
        self.logger.log(f"  - PMI 分项：{prosperity['pmi_index']}")

        # 2. 为每个产品计算开工率
        for idx, product_name in enumerate(self.util_products, 1):
            self.logger.log(f"[{idx}/{len(self.util_products)}] 计算开工率：{product_name}")

            # 查找该产品的配置信息
            product_cfg = self._find_product_config(product_name)
            tickers = product_cfg.get("tickers", []) if product_cfg else []

            # 使用整体景气度计算开工率
            # 后续可针对产品特性添加个性化调整因子
            utilization = self.prosperity_crawler.prosperity_to_utilization(
                prosperity["overall_index"]
            )

            record = {
                "product_name": product_name,
                "utilization_rate": round(utilization, 2),
                "week_change": 0.0,  # 暂时无周度变化数据
                "stat_date": self.today,
                "source": "ProsperityIndex",
                "prosperity_index": prosperity["overall_index"],
            }

            if tickers:
                record["tickers"] = ",".join(tickers)

            all_records.append(record)
            update_crawl_date(product_name, "utilization", self.today)
            self.logger.log(f"  开工率估算：{utilization:.1f}%", "SUCCESS")

        if not all_records:
            self.logger.log("没有产品需要爬取", "WARNING")
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        columns = [
            "product_name", "utilization_rate", "week_change",
            "stat_date", "source", "prosperity_index"
        ]
        if "tickers" in df.columns:
            columns.append("tickers")
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns]

    def _find_product_config(self, product_name):
        """从全量产品配置中查找匹配项"""
        for p in self.all_products:
            if p["name"] == product_name or product_name in p.get("keywords", []):
                return p
        return None


# ============== 独立运行入口 ==============
def main():
    """独立运行开工率爬虫"""
    crawler = OilchemUtilizationCrawler()
    df = crawler.run()

    if not df.empty:
        today_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(OUTPUT_DIR, f"chemical_utilization_{today_str}.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"数据已保存：{output_path}")

        latest_path = os.path.join(OUTPUT_DIR, "chemical_utilization.csv")
        df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"最新数据已保存：{latest_path}")
    else:
        crawler.logger.log("未获取到开工率数据")

    return df


if __name__ == "__main__":
    main()
