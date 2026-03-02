#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 AkShare 的化工期货现货价格爬虫 - 直接指定日期版本
数据源：AkShare futures_spot_price (期货现货价格接口)
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, OUTPUT_DIR


class AkShareChemFuturesCrawler(BaseCrawler):
    """AkShare 化工期货现货价格爬虫"""

    # 化工产品映射（期货符号 -> 产品信息）
    CHEM_PRODUCTS = {
        # ========== 化纤 ===========
        "TA": {"name": "PTA", "category": "化纤", "tickers": ["600346", "000703", "002493"]},
        "PF": {"name": "短纤", "category": "化纤", "tickers": ["600346", "002493"]},
        "EG": {"name": "乙二醇", "category": "化纤", "tickers": ["600346", "002493", "600426"]},
        # ========== 氯碱 ===========
        "V": {"name": "PVC", "category": "氯碱", "tickers": ["002092", "600075", "601216"]},
        "SH": {"name": "烧碱", "category": "氯碱", "tickers": ["600618", "601678"]},
        # ========== 煤化工 ===========
        "MA": {"name": "甲醇", "category": "煤化工", "tickers": ["600989", "600426", "600188"]},
        "UR": {"name": "尿素", "category": "煤化工", "tickers": ["600426", "600691"]},
        "J": {"name": "焦炭", "category": "煤化工", "tickers": ["600740", "000983"]},
        "JM": {"name": "焦煤", "category": "煤化工", "tickers": ["000983", "601666"]},
        # ========== 橡胶 ===========
        "RU": {"name": "橡胶", "category": "橡胶", "tickers": ["600466", "002408"]},
        "BR": {"name": "合成橡胶", "category": "橡胶", "tickers": ["002408"]},
        # ========== 炼化 ===========
        "FU": {"name": "燃油", "category": "炼化", "tickers": ["600028", "601857"]},
        "BU": {"name": "沥青", "category": "炼化", "tickers": ["600028", "601857"]},
        "PP": {"name": "聚丙烯", "category": "炼化", "tickers": ["002493", "600346"]},
        # ========== 建材 ===========
        "FG": {"name": "玻璃", "category": "建材", "tickers": ["600876", "000012"]},
        "SA": {"name": "纯碱", "category": "建材", "tickers": ["000683", "000822", "600409"]},
        # ========== 其他 ===========
        "SP": {"name": "纸浆", "category": "造纸", "tickers": ["002078", "600308"]},
        "SF": {"name": "硅铁", "category": "铁合金", "tickers": ["000612"]},
        "SM": {"name": "锰硅", "category": "铁合金", "tickers": ["000612"]},
        "EB": {"name": "苯乙烯", "category": "石化", "tickers": ["600346", "002493"]},
    }

    def __init__(self):
        super().__init__(name="AkShareChemFutures")
        # 动态获取当天日期
        self.trade_date = datetime.now().strftime("%Y%m%d")

    def crawl(self):
        """爬取所有化工产品价格"""
        all_records = []

        import akshare as ak

        # 获取指定日期的现货价格数据
        self.logger.log(f"获取 {self.trade_date} 期货现货价格数据...")
        try:
            spot_df = ak.futures_spot_price(date=self.trade_date)
            if spot_df is None or spot_df.empty:
                self.logger.log("无法获取期货现货价格数据", "ERROR")
                return pd.DataFrame()
        except Exception as e:
            self.logger.log(f"获取数据失败：{e}", "ERROR")
            return pd.DataFrame()

        self.logger.log(f"获取到 {len(spot_df)} 条期货现货价格数据")

        # 遍历每个化工品种，从现货数据中提取
        for symbol, config in self.CHEM_PRODUCTS.items():
            product_name = config["name"]
            category = config["category"]
            tickers = config["tickers"]

            # 在现货数据中查找匹配的品种
            matched = spot_df[spot_df["symbol"] == symbol]

            if not matched.empty:
                row = matched.iloc[0]
                spot_price = float(row.get("spot_price", 0))
                dom_price = float(row.get("dominant_contract_price", 0))

                # 优先使用现货价格，如果没有则用主力合约价格
                price = spot_price if spot_price > 0 else dom_price

                if self.validate_price(price, product_name):
                    all_records.append({
                        "product_name": product_name,
                        "product_category": category,
                        "price": round(price, 2),
                        "price_change": 0.0,
                        "unit": "元/吨",
                        "region": "全国",
                        "trade_date": self.trade_date[:4] + "-" + self.trade_date[4:6] + "-" + self.trade_date[6:],
                        "source": "AkShare",
                        "tickers": ",".join(tickers),
                    })
                    self.logger.log(f"  ✓ {product_name}: {price:.2f} 元/吨", "SUCCESS")
                else:
                    self.logger.log(f"  ✗ {product_name}: 价格异常 ({price})", "WARNING")
            else:
                self.logger.log(f"  ✗ {product_name}: 未找到", "WARNING")

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


# ============== 独立运行入口 ==============
def main():
    """独立运行爬虫"""
    crawler = AkShareChemFuturesCrawler()
    df = crawler.run()

    if not df.empty:
        today_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(OUTPUT_DIR, f"chemical_prices_{today_str}.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"数据已保存：{output_path}")

        # 同时保存一份最新版本（不带日期）
        latest_path = os.path.join(OUTPUT_DIR, "chemical_prices.csv")
        df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"最新数据已保存：{latest_path}")

        # 打印摘要
        print("\n" + "=" * 60)
        print("爬取结果摘要")
        print("=" * 60)
        print(f"总记录数：{len(df)}")
        print(f"产品种类：{df['product_name'].nunique()}")
        print(f"价格范围：{df['price'].min():.2f} - {df['price'].max():.2f} 元/吨")
        print("\n产品列表:")
        for product in df['product_name'].unique():
            prod_df = df[df['product_name'] == product]
            avg_price = prod_df['price'].mean()
            print(f"   {product}: {avg_price:.2f} 元/吨")
    else:
        crawler.logger.log("未获取到数据", "WARNING")

    return df


if __name__ == "__main__":
    main()
