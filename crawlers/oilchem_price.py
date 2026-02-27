#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
隆众资讯化工产品价格爬虫
数据源: oilchem.net 价格行情页
备选源: AkShare 化工数据接口
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import (
    BaseCrawler, OUTPUT_DIR, load_products_config,
    get_last_crawl_date, update_crawl_date
)
from parsers.oilchem_parser import parse_price_table, parse_json_price_data


class OilchemPriceCrawler(BaseCrawler):
    """隆众资讯价格爬虫"""

    # 隆众价格行情基础 URL
    BASE_URL = "https://www.oilchem.net"
    PRICE_URL = "https://www.oilchem.net/price/"

    def __init__(self):
        super().__init__(name="OilchemPrice")
        self.products = self.config.get("products", [])
        self.today = datetime.now().strftime("%Y-%m-%d")

    def crawl(self):
        """爬取所有产品价格"""
        all_records = []

        self.logger.log(f"待爬取产品数: {len(self.products)}")

        for idx, product in enumerate(self.products, 1):
            name = product["name"]
            category = product["category"]
            keywords = product.get("keywords", [name])
            tickers = product.get("tickers", [])

            self.logger.log(f"[{idx}/{len(self.products)}] 正在爬取: {name} ({category})")

            # 优先尝试隆众资讯
            records = self._crawl_oilchem_price(name, category, keywords)

            # 备选: AkShare
            if not records:
                records = self._crawl_akshare_price(name, category, keywords)

            if records:
                for r in records:
                    r["product_category"] = category
                    r["trade_date"] = self.today
                    r["source"] = r.get("source", "隆众资讯")
                    # 关联股票代码
                    r["tickers"] = ",".join(tickers)
                all_records.extend(records)
                update_crawl_date(name, "price", self.today)
                self.logger.log(f"  获取 {len(records)} 条价格数据", "SUCCESS")
            else:
                self.logger.log(f"  未获取到数据", "WARNING")

            self.sleep(2, 5)

        if not all_records:
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        # 标准化列顺序
        columns = [
            "product_name", "product_category", "price", "price_change",
            "unit", "region", "trade_date", "source", "tickers"
        ]
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns]

    def _crawl_oilchem_price(self, name, category, keywords):
        """从隆众资讯爬取价格"""
        records = []
        for keyword in keywords:
            # 尝试搜索页面
            search_url = f"{self.BASE_URL}/search/?keyword={keyword}&type=price"
            resp = self.safe_request(search_url)
            if resp is None:
                continue

            parsed = parse_price_table(resp.text, product_name=name)
            if parsed:
                records.extend(parsed)
                break

            self.sleep(1, 2)

        return records

    def _crawl_akshare_price(self, name, category, keywords):
        """备选方案: 通过 AkShare 获取化工价格"""
        try:
            import akshare as ak
        except ImportError:
            self.logger.log("AkShare 未安装，跳过备选数据源", "WARNING")
            return []

        records = []
        try:
            # 尝试 AkShare 化工现货价格接口
            for keyword in keywords:
                try:
                    df = ak.futures_spot_price(date=self.today.replace("-", ""))
                    if df is not None and not df.empty:
                        # 按关键词过滤
                        mask = df.apply(
                            lambda row: any(kw in str(row) for kw in [keyword]),
                            axis=1
                        )
                        matched = df[mask]
                        for _, row in matched.iterrows():
                            price = None
                            for col in df.columns:
                                if "价" in col or "price" in col.lower():
                                    try:
                                        price = float(row[col])
                                        break
                                    except (ValueError, TypeError):
                                        continue
                            if price and self.validate_price(price, name):
                                records.append({
                                    "product_name": name,
                                    "price": round(price, 2),
                                    "price_change": 0.0,
                                    "unit": "元/吨",
                                    "region": "全国",
                                    "source": "AkShare",
                                })
                        if records:
                            break
                except Exception:
                    continue
        except Exception as e:
            self.logger.log(f"AkShare 获取失败: {name} - {e}", "WARNING")

        return records


# ============== 独立运行入口 ==============
def main():
    """独立运行价格爬虫"""
    crawler = OilchemPriceCrawler()
    df = crawler.run()

    if not df.empty:
        today_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(OUTPUT_DIR, f"chemical_prices_{today_str}.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"数据已保存: {output_path}")

        # 同时保存一份最新版本（不带日期）
        latest_path = os.path.join(OUTPUT_DIR, "chemical_prices.csv")
        df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"最新数据已保存: {latest_path}")

    return df


if __name__ == "__main__":
    main()
