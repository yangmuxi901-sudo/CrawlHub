#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
化工景气度指数爬虫
通过组合指标法构建替代开工率指标体系

数据源：
  1. 同花顺行业指数（AkShare）
  2. 期货库存数据（AkShare）
  3. 期货价格数据（AkShare）
  4. 宏观 PMI 数据（AkShare）
"""

import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, load_products_config


class ProsperityIndexCrawler(BaseCrawler):
    """
    化工景气度指数爬虫

    通过以下指标计算行业景气度：
    1. 行业指数（同花顺）
    2. 期货库存（反向指标）
    3. 产品价差（价格 - 原料成本）
    4. 宏观 PMI

    景气度 = (价格分位数 + 行业指数分位数 - 库存分位数 + PMI 分位数) / 4
    """

    def __init__(self):
        super().__init__(name="ProsperityIndex")
        self.config = load_products_config()

        # 化工相关行业指数代码（同花顺）
        self.industry_codes = {
            "化学纤维": "801032",
            "化学原料": "801033",
            "化学制品": "801034",
            "塑料": "801036",
            "橡胶": "801037",
        }

        # 化工相关期货品种
        self.chem_futures = ["TA", "MA", "V", "RU", "PP", "PE", "FG", "SA"]

        # 原料价格（用于计算价差）
        self.raw_materials = ["原油", "煤炭", "天然气"]

    def get_industry_index(self, industry_name: str = None) -> pd.DataFrame:
        """
        获取同花顺行业指数

        Args:
            industry_name: 行业名称，如"化学原料"，为 None 时返回所有化工行业

        Returns:
            DataFrame(trade_date, index_value, change_pct)
        """
        try:
            import akshare as ak

            results = []

            if industry_name:
                # 获取指定行业
                if industry_name in self.industry_codes:
                    codes_to_fetch = {industry_name: self.industry_codes[industry_name]}
                else:
                    self.logger.log(f"未知行业：{industry_name}", "WARNING")
                    return pd.DataFrame()
            else:
                # 获取所有化工行业
                codes_to_fetch = self.industry_codes

            for name, code in codes_to_fetch.items():
                try:
                    # 获取行业指数实时数据
                    df = ak.index_realtime_sw(symbol="二级行业")
                    if df is not None and not df.empty:
                        # 查找匹配的行业
                        matched = df[df["指数代码"] == code]
                        if not matched.empty:
                            row = matched.iloc[0]
                            results.append({
                                "industry_name": name,
                                "trade_date": datetime.now().strftime("%Y-%m-%d"),
                                "index_value": float(row["最新价"]) if "最新价" in row else 0,
                                "change_pct": float(row["涨跌幅"]) if "涨跌幅" in row else 0,
                            })
                except Exception as e:
                    self.logger.log(f"获取行业 {name} 指数失败：{e}", "WARNING")

            if not results:
                # 如果实时接口失败，尝试使用历史数据接口
                return self._get_industry_index_history()

            return pd.DataFrame(results)

        except Exception as e:
            self.logger.log(f"获取行业指数异常：{e}", "ERROR")
            return pd.DataFrame()

    def _get_industry_index_history(self) -> pd.DataFrame:
        """获取行业指数历史数据（备用方案）"""
        try:
            import akshare as ak

            results = []
            for name, code in self.industry_codes.items():
                try:
                    # 获取历史数据
                    df = ak.index_stock_cons_sw(symbol="二级行业")
                    if df is not None and not df.empty:
                        results.append({
                            "industry_name": name,
                            "trade_date": datetime.now().strftime("%Y-%m-%d"),
                            "index_value": df["close"].iloc[-1] if "close" in df.columns else 0,
                            "change_pct": 0,
                        })
                except Exception:
                    continue

            return pd.DataFrame(results) if results else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_futures_inventory(self, product_name: str = None) -> pd.DataFrame:
        """
        获取期货库存数据

        Args:
            product_name: 产品名称，为 None 时返回所有

        Returns:
            DataFrame(product_name, inventory, change)
        """
        try:
            import akshare as ak

            results = []

            # 获取期货库存数据
            df = ak.futures_inventory_99()
            if df is None or df.empty:
                return pd.DataFrame()

            # 筛选化工相关产品
            chem_keywords = ["PTA", "甲醇", "PVC", "橡胶", "塑料", "聚丙烯", "聚乙烯", "玻璃", "纯碱", "纸浆", "苯乙烯"]

            for _, row in df.iterrows():
                name = str(row.get("品种", ""))
                # 检查是否为化工产品
                is_chem = any(kw in name for kw in chem_keywords)
                if is_chem:
                    inventory = row.get("库存", 0)
                    try:
                        inventory = float(inventory) if inventory else 0
                    except (ValueError, TypeError):
                        inventory = 0

                    results.append({
                        "product_name": name,
                        "inventory": inventory,
                        "change": 0,  # 库存变化
                    })

            return pd.DataFrame(results)

        except Exception as e:
            self.logger.log(f"获取期货库存异常：{e}", "ERROR")
            return pd.DataFrame()

    def get_futures_prices(self) -> Dict[str, float]:
        """
        获取期货价格数据

        Returns:
            Dict[product_name, price]
        """
        try:
            import akshare as ak

            # 获取期货现货价格
            df = ak.futures_spot_price(date=datetime.now().strftime("%Y%m%d"))
            if df is None or df.empty:
                return {}

            prices = {}
            for _, row in df.iterrows():
                name = str(row.get("品种", ""))
                price = row.get("最新价", 0)
                try:
                    price = float(price) if price else 0
                except (ValueError, TypeError):
                    price = 0
                prices[name] = price

            return prices

        except Exception as e:
            self.logger.log(f"获取期货价格异常：{e}", "ERROR")
            return {}

    def get_raw_material_prices(self) -> Dict[str, float]:
        """
        获取原料价格（原油、煤炭等）

        Returns:
            Dict[material_name, price]
        """
        try:
            import akshare as ak

            prices = {}

            # 获取原油价格
            try:
                oil_df = ak.energy_oil_detail(date=datetime.now().strftime("%Y%m%d"))
                if oil_df is not None and not oil_df.empty:
                    prices["原油"] = float(oil_df["价格"].iloc[-1]) if "价格" in oil_df.columns else 0
            except Exception:
                prices["原油"] = 80  # 默认值（美元/桶）

            # 煤炭价格（环渤海动力煤）
            try:
                coal_df = ak.futures_spot_price(symbol="动力煤")
                if coal_df is not None and not coal_df.empty:
                    prices["煤炭"] = float(coal_df["最新价"].iloc[-1]) if "最新价" in coal_df.columns else 800
            except Exception:
                prices["煤炭"] = 800  # 默认值（元/吨）

            return prices

        except Exception as e:
            self.logger.log(f"获取原料价格异常：{e}", "ERROR")
            return {"原油": 80, "煤炭": 800}

    def calculate_price_spread(self) -> Dict[str, float]:
        """
        计算产品价差（产品价格 - 原料成本）

        Returns:
            Dict[product_name, spread]
        """
        futures_prices = self.get_futures_prices()
        raw_materials = self.get_raw_material_prices()

        spreads = {}

        # 简化计算：用产品价格减去平均原料成本
        avg_raw_material = sum(raw_materials.values()) / len(raw_materials) if raw_materials else 0

        for product, price in futures_prices.items():
            # 价差 = 产品价格 - 原料成本（简化计算）
            spread = price - avg_raw_material * 10  # 简单放大系数
            spreads[product] = spread

        return spreads

    def get_pmi(self) -> float:
        """
        获取宏观 PMI 数据

        Returns:
            PMI 值（0-100）
        """
        try:
            import akshare as ak

            # 获取中国 PMI 数据
            df = ak.macro_china_pmi()
            if df is not None and not df.empty:
                # 获取最新的 PMI
                pmi = float(df[" PMI"].iloc[-1]) if " PMI" in df.columns else 50
                return pmi

            return 50  # 默认值（荣枯线）

        except Exception as e:
            self.logger.log(f"获取 PMI 异常：{e}", "WARNING")
            return 50

    def compute_prosperity_index(self) -> Dict:
        """
        计算综合景气度指数

        Returns:
            Dict {
                "overall_index": 整体景气度 (0-100),
                "industry_index": 行业分项,
                "inventory_index": 库存分项,
                "pmi_index": PMI 分项
            }
        """
        # 1. 获取行业指数
        industry_df = self.get_industry_index()

        # 2. 获取库存数据
        inventory_df = self.get_futures_inventory()

        # 3. 获取 PMI
        pmi = self.get_pmi()

        # 4. 计算各分项指数（标准化为 0-100）

        # 行业指数分项（越高越景气）
        if not industry_df.empty:
            avg_index = industry_df["index_value"].mean()
            # 标准化：假设行业指数在 3000-10000 范围
            industry_score = min(100, max(0, (avg_index - 3000) / 70))
        else:
            industry_score = 50  # 默认中性

        # 库存分项（越低越景气，反向指标）
        if not inventory_df.empty:
            total_inventory = inventory_df["inventory"].sum()
            # 标准化：假设库存 in 100-500 万吨
            inventory_score = min(100, max(0, (500 - total_inventory) / 4))
        else:
            inventory_score = 50

        # PMI 分项（本身就是 0-100）
        pmi_score = pmi

        # 5. 综合计算
        overall_index = (industry_score + inventory_score + pmi_score) / 3

        return {
            "overall_index": round(overall_index, 2),
            "industry_index": round(industry_score, 2),
            "inventory_index": round(inventory_score, 2),
            "pmi_index": round(pmi_score, 2),
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
        }

    def prosperity_to_utilization(self, prosperity_index: float) -> float:
        """
        将景气度指数转换为开工率

        映射逻辑：
        - 景气度 0 -> 开工率 50%（最低开工水平）
        - 景气度 50 -> 开工率 72.5%（行业中枢）
        - 景气度 100 -> 开工率 95%（满负荷生产）

        线性映射公式：
        开工率 = 50 + (景气度 / 100) * 45

        Args:
            prosperity_index: 景气度指数 (0-100)

        Returns:
            开工率 (50-95%)
        """
        # 确保输入在合理范围
        prosperity_index = max(0, min(100, prosperity_index))

        # 线性映射
        utilization = 50 + (prosperity_index / 100) * 45

        # 限制在 50-95% 范围
        return max(50, min(95, utilization))

    def get_utilization_estimate(self, product_name: str = None) -> Dict:
        """
        获取开工率估算值

        Args:
            product_name: 产品名称，为 None 时返回整体估算

        Returns:
            Dict {
                "product_name": str,
                "utilization_rate": float,
                "prosperity_index": float,
                "trade_date": str
            }
        """
        prosperity = self.compute_prosperity_index()
        utilization = self.prosperity_to_utilization(prosperity["overall_index"])

        return {
            "product_name": product_name or "化工整体",
            "utilization_rate": round(utilization, 2),
            "prosperity_index": prosperity["overall_index"],
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
        }

    def crawl(self) -> pd.DataFrame:
        """
        爬取开工率替代数据

        Returns:
            DataFrame(product_name, utilization_rate, prosperity_index, trade_date)
        """
        self.logger.log("开始计算化工行业开工率估算值...")

        # 获取整体估算
        overall = self.get_utilization_estimate()

        results = [overall]

        # 为主要产品计算分项估算
        products_config = self.config.get("utilization_products", [])

        for product in products_config:
            # 目前使用整体景气度，后续可针对产品特性调整
            product_result = overall.copy()
            product_result["product_name"] = product
            results.append(product_result)

        df = pd.DataFrame(results)

        self.logger.log(f"计算完成，共 {len(df)} 条记录")
        self.logger.log(f"整体开工率估算：{overall['utilization_rate']}%")

        return df


# ============== 独立运行入口 ==============
def main():
    """独立运行景气度爬虫"""
    crawler = ProsperityIndexCrawler()
    df = crawler.run()

    if not df.empty:
        today_str = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join("output", f"prosperity_index_{today_str}.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        crawler.logger.log(f"数据已保存：{output_path}")

    return df


if __name__ == "__main__":
    main()
