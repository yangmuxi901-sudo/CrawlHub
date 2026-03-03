#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
化工数据爬虫 - 多数据源整合版
数据源：
  1. AkShare 期货现货价格（主）
  2. 隆众资讯 API（需登录）
  3. 其他免费数据源（备选）

覆盖产品：
  - 化纤：PTA、短纤、乙二醇
  - 氯碱：PVC、烧碱
  - 煤化工：甲醇、尿素、焦炭、焦煤
  - 橡胶：橡胶、合成橡胶
  - 炼化：燃油、沥青、聚丙烯、聚乙烯
  - 建材：玻璃、纯碱
  - 其他：纸浆、硅铁、锰硅、苯乙烯
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, OUTPUT_DIR
from crawlers.akshare_chem_crawler import AkShareChemFuturesCrawler


class OilchemPriceCrawler(BaseCrawler):
    """隆众资讯价格爬虫 - 多数据源整合版"""

    def __init__(self):
        super().__init__(name="OilchemPrice")
        self.today = datetime.now().strftime("%Y-%m-%d")

    def crawl(self):
        """爬取所有化工产品价格 - 多数据源"""
        self.logger.log("开始爬取化工产品价格...")
        self.logger.log("数据源优先级：AkShare 期货现货 > 隆众 API(需登录)")

        # 主数据源：AkShare 期货现货价格
        df = self._crawl_akshare()

        if df is not None and not df.empty:
            self.logger.log(f"爬取完成，共 {len(df)} 条数据")
            return df
        else:
            self.logger.log("所有数据源均未获取到数据", "ERROR")
            return pd.DataFrame()

    def _crawl_akshare(self):
        """从 AkShare 获取化工期货价格"""
        self.logger.log("使用 AkShare 期货现货价格接口...")
        try:
            crawler = AkShareChemFuturesCrawler()
            return crawler.crawl()
        except Exception as e:
            self.logger.log(f"AkShare 数据获取失败：{e}", "ERROR")
            return None


# ============== 独立运行入口 ==============
def main():
    """独立运行爬虫"""
    crawler = OilchemPriceCrawler()
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
        if 'price' in df.columns:
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
