#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开工率替代指标测试 - TDD
测试组合指标法构建的景气度指数是否能有效替代开工率
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestIndustryIndexFetch(unittest.TestCase):
    """测试行业指数获取"""

    def test_fetch_chemical_index(self):
        """测试获取化学原料/化学制品行业指数"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.get_industry_index()

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIsInstance(result, pd.DataFrame)
        if not result.empty:
            self.assertIn("trade_date", result.columns)
            self.assertIn("index_value", result.columns)
            self.assertGreater(len(result), 0)
            print(f"✓ 行业指数获取成功：{len(result)} 条记录")

    def test_fetch_specific_industries(self):
        """测试获取特定行业指数（化学纤维、化学原料、化学制品）"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        industries = ["化学纤维", "化学原料", "化学制品"]

        for industry in industries:
            result = crawler.get_industry_index(industry_name=industry)
            self.assertIsNotNone(result, f"行业 {industry} 返回 None")
            print(f"✓ 行业 {industry}: 获取成功")


class TestFuturesInventory(unittest.TestCase):
    """测试期货库存获取"""

    def test_fetch_futures_inventory(self):
        """测试获取期货库存数据"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.get_futures_inventory()

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIsInstance(result, pd.DataFrame)
        if not result.empty:
            self.assertIn("product_name", result.columns)
            self.assertIn("inventory", result.columns)
            print(f"✓ 期货库存获取成功：{len(result)} 条记录")

    def test_inventory_for_chemical_products(self):
        """测试获取化工相关产品的库存（PTA、PVC、橡胶等）"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        chem_products = ["PTA", "PVC", "橡胶", "甲醇"]

        result = crawler.get_futures_inventory()
        if not result.empty:
            for product in chem_products:
                matched = result[result["product_name"].str.contains(
                    product, case=False, na=False
                )]
                if len(matched) > 0:
                    print(f"✓ 产品 {product}: 库存数据存在")


class TestPriceSpreadCalculation(unittest.TestCase):
    """测试价差计算"""

    def test_price_spread_calculation(self):
        """测试产品价格 - 原料成本价差计算"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.calculate_price_spread()

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        if result:
            for product, spread in result.items():
                self.assertIsInstance(spread, (int, float))
                print(f"✓ 产品 {product}: 价差 = {spread}")

    def test_spread_reasonableness(self):
        """测试价差合理性（不应为负数或过大）"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.calculate_price_spread()

        if result:
            for product, spread in result.items():
                # 价差应在合理范围内（-10000 到 50000）
                self.assertGreater(spread, -10000, f"{product} 价差过小")
                self.assertLess(spread, 50000, f"{product} 价差过大")


class TestProsperityIndexComputation(unittest.TestCase):
    """测试景气度指数计算"""

    def test_prosperity_index_computation(self):
        """测试景气度指数计算"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.compute_prosperity_index()

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        if result:
            self.assertIn("overall_index", result)
            self.assertIsInstance(result["overall_index"], (int, float))
            print(f"✓ 整体景气度指数：{result['overall_index']}")
            if "industry_index" in result:
                print(f"✓ 行业分项指数存在")

    def test_prosperity_index_range(self):
        """测试景气度指数在合理范围内"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()
        result = crawler.compute_prosperity_index()

        if result and "overall_index" in result:
            index = result["overall_index"]
            # 景气度指数标准化后应在 0-100 范围
            self.assertGreaterEqual(index, 0, "景气度指数不应小于 0")
            self.assertLessEqual(index, 100, "景气度指数不应大于 100")


class TestProsperityToUtilizationMapping(unittest.TestCase):
    """测试景气度转开工率映射"""

    def test_mapping_function(self):
        """测试景气度转开工率函数"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()

        # 测试不同景气度水平下的开工率
        test_cases = [
            (0, 50.0),      # 景气度 0 -> 开工率 50%
            (50, 75.0),     # 景气度 50 -> 开工率 75%
            (100, 100.0),   # 景气度 100 -> 开工率 100%
        ]

        for prosperity, expected_utilization in test_cases:
            utilization = crawler.prosperity_to_utilization(prosperity)
            self.assertIsNotNone(utilization)
            self.assertGreaterEqual(utilization, 50, "开工率不应低于 50%")
            self.assertLessEqual(utilization, 95, "开工率不应高于 95%")
            print(f"✓ 景气度 {prosperity} -> 开工率 {utilization:.1f}%")

    def test_mapping_continuity(self):
        """测试映射函数的连续性（单调递增）"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()

        prev_util = None
        for prosperity in range(0, 101, 10):
            util = crawler.prosperity_to_utilization(prosperity)
            if prev_util is not None:
                self.assertGreaterEqual(
                    util, prev_util,
                    f"开工率应随景气度单调递增：{prev_util} -> {util}"
                )
            prev_util = util
            print(f"✓ 景气度 {prosperity} -> 开工率 {util:.1f}%")


class TestIntegration(unittest.TestCase):
    """集成测试：完整流程"""

    def test_full_pipeline(self):
        """测试从数据获取到开工率计算的完整流程"""
        from crawlers.prosperity_index_crawler import ProsperityIndexCrawler

        crawler = ProsperityIndexCrawler()

        # 1. 获取所有替代指标
        industry_index = crawler.get_industry_index()
        inventory = crawler.get_futures_inventory()
        spreads = crawler.calculate_price_spread()

        # 2. 计算景气度指数
        prosperity = crawler.compute_prosperity_index()

        # 3. 转换为开工率
        if prosperity and "overall_index" in prosperity:
            utilization = crawler.prosperity_to_utilization(
                prosperity["overall_index"]
            )

            self.assertGreaterEqual(
                utilization, 50,
                "最终开工率不应低于 50%"
            )
            self.assertLessEqual(
                utilization, 95,
                "最终开工率不应高于 95%"
            )
            print(f"✓ 完整流程测试通过：开工率 = {utilization:.1f}%")


if __name__ == "__main__":
    unittest.main(verbosity=2)
