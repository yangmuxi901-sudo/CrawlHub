#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
隆众资讯化工开工率爬虫
数据源: oilchem.net 行业报告/周报
备选源: AkShare
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import (
    BaseCrawler, OUTPUT_DIR, load_products_config,
    get_last_crawl_date, update_crawl_date
)
from parsers.oilchem_parser import parse_utilization_table


class OilchemUtilizationCrawler(BaseCrawler):
    """隆众资讯开工率爬虫"""

    BASE_URL = "https://www.oilchem.net"

    def __init__(self):
        super().__init__(name="OilchemUtilization")
        self.util_products = self.config.get("utilization_products", [])
        self.all_products = self.config.get("products", [])
        self.today = datetime.now().strftime("%Y-%m-%d")

    def crawl(self):
        """爬取开工率数据"""
        all_records = []

        self.logger.log(f"待爬取开工率产品数: {len(self.util_products)}")

        for idx, product_name in enumerate(self.util_products, 1):
            self.logger.log(f"[{idx}/{len(self.util_products)}] 正在爬取开工率: {product_name}")

            # 查找该产品的配置信息
            product_cfg = self._find_product_config(product_name)
            keywords = product_cfg.get("keywords", [product_name]) if product_cfg else [product_name]

            # 优先隆众资讯
            records = self._crawl_oilchem_utilization(product_name, keywords)

            # 备选: AkShare
            if not records:
                records = self._crawl_akshare_utilization(product_name, keywords)

            if records:
                for r in records:
                    r["stat_date"] = self.today
                    r["source"] = r.get("source", "隆众资讯")
                all_records.extend(records)
                update_crawl_date(product_name, "utilization", self.today)
                self.logger.log(f"  获取 {len(records)} 条开工率数据", "SUCCESS")
            else:
                self.logger.log(f"  未获取到数据", "WARNING")

            self.sleep(2, 5)

        if not all_records:
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        columns = [
            "product_name", "utilization_rate", "week_change",
            "stat_date", "source"
        ]
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

    def _crawl_oilchem_utilization(self, product_name, keywords):
        """从隆众资讯爬取开工率"""
        records = []
        for keyword in keywords:
            search_url = f"{self.BASE_URL}/search/?keyword={keyword}开工率&type=report"
            resp = self.safe_request(search_url)
            if resp is None:
                continue

            parsed = parse_utilization_table(resp.text, product_name=product_name)
            if parsed:
                # 校验数据
                for r in parsed:
                    if self.validate_rate(r.get("utilization_rate"), product_name):
                        records.append(r)
                if records:
                    break

            self.sleep(1, 2)

        return records

    def _crawl_akshare_utilization(self, product_name, keywords):
        """备选方案: 通过 AkShare 获取开工率"""
        try:
            import akshare as ak
        except ImportError:
            self.logger.log("AkShare 未安装，跳过备选数据源", "WARNING")
            return []

        records = []
        try:
            # 尝试 AkShare 产能利用率接口
            for keyword in keywords:
                try:
                    df = ak.futures_inventory_em(symbol=keyword)
                    if df is not None and not df.empty:
                        for col in df.columns:
                            if "开工" in col or "利用" in col:
                                last_row = df.iloc[-1]
                                try:
                                    rate = float(last_row[col])
                                    if self.validate_rate(rate, product_name):
                                        records.append({
                                            "product_name": product_name,
                                            "utilization_rate": round(rate, 2),
                                            "week_change": 0.0,
                                            "source": "AkShare",
                                        })
                                except (ValueError, TypeError):
                                    continue
                    if records:
                        break
                except Exception:
                    continue
        except Exception as e:
            self.logger.log(f"AkShare 获取开工率失败: {product_name} - {e}", "WARNING")

        return records


# ============== 独立运行入口 ==============
def main():
    """独立运行开工率爬虫"""
    crawler = OilchemUtilizationCrawler()
    df = crawler.run()

    if not df.empty:
        today_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(OUTPUT_DIR, f"chemical_utilization_{today_str}.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"数据已保存: {output_path}")

        latest_path = os.path.join(OUTPUT_DIR, "chemical_utilization.csv")
        df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"最新数据已保存: {latest_path}")

    return df


if __name__ == "__main__":
    main()
