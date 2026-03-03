#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 AkShare 的化工期货价格爬虫 - 多数据源容错版

数据源优先级：
1. 期货实时行情 (futures_zh_realtime) - 最可靠
2. 期货现货价格 (futures_spot_price) - 备用

风控原则:
- 单个数据源失败不影响整体
- 单个产品失败不影响其他产品
- 至少返回部分可用数据
"""

import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.base import BaseCrawler, OUTPUT_DIR


class AkShareChemFuturesCrawler(BaseCrawler):
    """AkShare 化工期货价格爬虫 - 多数据源容错版"""

    # 化工产品映射（期货符号 -> 产品信息）
    CHEM_PRODUCTS = {
        # ========== 化纤 ==========
        "TA": {"name": "PTA", "category": "化纤", "tickers": ["600346", "000703", "002493"]},
        "PF": {"name": "短纤", "category": "化纤", "tickers": ["600346", "002493"]},
        "EG": {"name": "乙二醇", "category": "化纤", "tickers": ["600346", "002493", "600426"]},
        # ========== 氯碱 ==========
        "V": {"name": "PVC", "category": "氯碱", "tickers": ["002092", "600075", "601216"]},
        "SH": {"name": "烧碱", "category": "氯碱", "tickers": ["600618", "601678"]},
        # ========== 煤化工 ==========
        "MA": {"name": "甲醇", "category": "煤化工", "tickers": ["600989", "600426", "600188"]},
        "UR": {"name": "尿素", "category": "煤化工", "tickers": ["600426", "600691"]},
        "J": {"name": "焦炭", "category": "煤化工", "tickers": ["600740", "000983"]},
        "JM": {"name": "焦煤", "category": "煤化工", "tickers": ["000983", "601666"]},
        # ========== 橡胶 ==========
        "RU": {"name": "橡胶", "category": "橡胶", "tickers": ["600466", "002408"]},
        "BR": {"name": "合成橡胶", "category": "橡胶", "tickers": ["002408"]},
        # ========== 炼化 ==========
        "FU": {"name": "燃油", "category": "炼化", "tickers": ["600028", "601857"]},
        "BU": {"name": "沥青", "category": "炼化", "tickers": ["600028", "601857"]},
        "PP": {"name": "聚丙烯", "category": "炼化", "tickers": ["002493", "600346"]},
        "PE": {"name": "聚乙烯", "category": "炼化", "tickers": ["002493", "600346"]},
        # ========== 建材 ==========
        "FG": {"name": "玻璃", "category": "建材", "tickers": ["600876", "000012"]},
        "SA": {"name": "纯碱", "category": "建材", "tickers": ["000683", "000822", "600409"]},
        # ========== 其他 ==========
        "SP": {"name": "纸浆", "category": "造纸", "tickers": ["002078", "600308"]},
        "SF": {"name": "硅铁", "category": "铁合金", "tickers": ["000612"]},
        "SM": {"name": "锰硅", "category": "铁合金", "tickers": ["000612"]},
        "EB": {"name": "苯乙烯", "category": "石化", "tickers": ["600346", "002493"]},
    }

    def __init__(self):
        super().__init__(name="AkShareChemFutures")
        # 动态获取当天日期
        self.trade_date = datetime.now().strftime("%Y%m%d")

    def _fetch_futures_realtime(self) -> Optional[pd.DataFrame]:
        """
        数据源 1: 获取期货实时行情 (futures_zh_realtime)
        返回：DataFrame 包含 symbol, latest_price 等字段
        """
        try:
            import akshare as ak
            self.logger.log("尝试数据源 1: 期货实时行情 (futures_zh_realtime)...")

            df = ak.futures_zh_realtime()
            if df is not None and not df.empty and "symbol" in df.columns:
                # 提取主力合约（symbol 以 0 结尾的）
                main_df = df[df['symbol'].str.endswith('0', na=False)].copy()
                if not main_df.empty:
                    # 重命名列以匹配提取逻辑
                    main_df = main_df.rename(columns={'trade': 'spot_price', 'symbol': 'symbol'})
                    self.logger.log(f"  ✓ 获取成功：{len(main_df)} 条主力合约数据", "SUCCESS")
                    return main_df

            self.logger.log("  ✗ 数据为空或格式不符", "WARNING")
            return None
        except Exception as e:
            self.logger.log(f"  ✗ 获取失败：{e}", "WARNING")
            return None

    def _fetch_futures_spot_previous(self) -> Optional[pd.DataFrame]:
        """
        数据源 2: 获取期货现货价格（前一日数据，futures_spot_price_previous）
        返回：DataFrame 包含商品、现货价格、主力合约价格等字段
        """
        try:
            import akshare as ak
            self.logger.log("尝试数据源 2: 期货现货价格前一日 (futures_spot_price_previous)...")

            df = ak.futures_spot_price_previous()
            if df is not None and not df.empty and "商品" in df.columns:
                self.logger.log(f"  ✓ 获取成功：{len(df)} 条数据", "SUCCESS")
                return df

            self.logger.log("  ✗ 数据为空或格式不符", "WARNING")
            return None
        except Exception as e:
            self.logger.log(f"  ✗ 获取失败：{e}", "WARNING")
            return None

    def _fetch_futures_spot(self) -> Optional[pd.DataFrame]:
        """
        数据源 3: 获取期货现货价格 (futures_spot_price) - 最后尝试
        返回：DataFrame 包含 symbol, spot_price 等字段
        """
        try:
            import akshare as ak
            self.logger.log(f"尝试数据源 3: 期货现货价格 (futures_spot_price, date={self.trade_date})...")

            df = ak.futures_spot_price(date=self.trade_date)
            if df is not None and not df.empty and "symbol" in df.columns:
                self.logger.log(f"  ✓ 获取成功：{len(df)} 条数据", "SUCCESS")
                return df

            self.logger.log("  ✗ 数据为空或格式不符", "WARNING")
            return None
        except Exception as e:
            self.logger.log(f"  ✗ 获取失败：{e}", "WARNING")
            return None

    def _extract_product_price(self, df: pd.DataFrame, symbol: str, config: Dict) -> Optional[Dict]:
        """
        从 DataFrame 中提取单个产品的价格
        风控：即使单个产品提取失败，不影响其他产品
        """
        try:
            matched = df[df["symbol"] == symbol]
            if matched.empty:
                return None

            row = matched.iloc[0]

            # 尝试多个价格字段
            price = 0
            for price_field in ["latest_price", "spot_price", "dominant_contract_price", "current_price"]:
                if price_field in row and row[price_field]:
                    try:
                        price = float(row[price_field])
                        if price > 0:
                            break
                    except (ValueError, TypeError):
                        continue

            if price <= 0:
                return None

            if not self.validate_price(price, config["name"]):
                return None

            return {
                "product_name": config["name"],
                "product_category": config["category"],
                "price": round(price, 2),
                "price_change": 0.0,
                "unit": "元/吨",
                "region": "全国",
                "trade_date": f"{self.trade_date[:4]}-{self.trade_date[4:6]}-{self.trade_date[6:]}",
                "source": "AkShare",
                "tickers": ",".join(config["tickers"]),
            }
        except Exception as e:
            self.logger.log(f"  ✗ {config['name']} 提取失败：{e}", "DEBUG")
            return None

    def crawl(self) -> pd.DataFrame:
        """
        爬取所有化工产品价格 - 多数据源 + 容错

        数据源优先级:
        1. futures_spot_price_previous (最可靠，每日更新)
        2. futures_zh_realtime (期货实时行情)
        3. futures_spot_price (当日现货价格，可能失败)

        风控策略:
        1. 多个数据源依次尝试，一个失败不影响其他
        2. 单个产品失败不影响其他产品
        3. 至少返回部分可用数据，不轻易返回空
        """
        all_records: List[Dict] = []

        # ========== 步骤 1: 尝试多个数据源获取数据 ==========
        price_df: Optional[pd.DataFrame] = None

        # 数据源 1: 期货现货价格前一日（最可靠）
        price_df = self._fetch_futures_spot_previous()

        # 数据源 2: 期货实时行情
        if price_df is None:
            price_df = self._fetch_futures_realtime()

        # 数据源 3: 期货现货价格（当日）
        if price_df is None:
            price_df = self._fetch_futures_spot()

        # 所有数据源都失败
        if price_df is None:
            self.logger.log("所有数据源均失败，返回空数据", "ERROR")
            return pd.DataFrame()

        self.logger.log(f"获取到 {len(price_df)} 条价格数据，开始提取化工产品...")

        # ========== 步骤 2: 根据数据源类型提取化工产品 ==========
        success_count = 0
        fail_count = 0

        # 检查是否是 futures_spot_price_previous 格式
        if "商品" in price_df.columns and "现货价格" in price_df.columns:
            # 使用 futures_spot_price_previous 数据
            all_records = self._extract_from_spot_previous(price_df)
        else:
            # 使用通用提取逻辑
            for symbol, config in self.CHEM_PRODUCTS.items():
                result = self._extract_product_price(price_df, symbol, config)
                if result:
                    all_records.append(result)
                    success_count += 1
                else:
                    fail_count += 1

        # ========== 步骤 3: 返回结果 ==========
        if not all_records:
            self.logger.log("未提取到任何化工产品价格，但数据源可能仍可用", "WARNING")
            return pd.DataFrame()

        df = pd.DataFrame(all_records)
        self.logger.log(f"成功提取 {success_count} 种产品，失败 {fail_count} 种", "SUCCESS")

        # 标准化列顺序
        columns = [
            "product_name", "product_category", "price", "price_change",
            "unit", "region", "trade_date", "source", "tickers"
        ]
        for col in columns:
            if col not in df.columns:
                df[col] = ""

        return df[columns]

    def _extract_from_spot_previous(self, df: pd.DataFrame) -> List[Dict]:
        """
        从 futures_spot_price_previous 数据中提取化工产品
        """
        all_records = []
        success_count = 0
        fail_count = 0

        for symbol, config in self.CHEM_PRODUCTS.items():
            try:
                # 在商品名称中查找匹配
                matched = df[df["商品"].str.contains(config["name"], na=False)]

                if matched.empty:
                    # 尝试用期货代码匹配
                    if symbol in ["TA", "V", "MA", "RU", "PP", "PE", "FG", "SA", "EG", "PF"]:
                        matched = df[df["主力合约代码"].str.startswith(symbol, na=False)]

                if not matched.empty:
                    row = matched.iloc[0]
                    # 优先使用现货价格
                    price_str = str(row.get("现货价格", ""))
                    try:
                        price = float(price_str.replace(",", ""))
                    except (ValueError, AttributeError):
                        # 如果现货价格不可用，使用主力合约价格
                        price = float(row.get("主力合约价格", 0))

                    if price > 0 and self.validate_price(price, config["name"]):
                        all_records.append({
                            "product_name": config["name"],
                            "product_category": config["category"],
                            "price": round(price, 2),
                            "price_change": float(row.get("主力合约变动百分比", 0) or 0) * 100,
                            "unit": "元/吨",
                            "region": "全国",
                            "trade_date": datetime.now().strftime("%Y-%m-%d"),
                            "source": "AkShare",
                            "tickers": ",".join(config["tickers"]),
                        })
                        self.logger.log(f"  ✓ {config['name']}: {price:.2f} 元/吨", "SUCCESS")
                        success_count += 1
                    else:
                        self.logger.log(f"  ✗ {config['name']}: 价格异常", "WARNING")
                        fail_count += 1
                else:
                    self.logger.log(f"  ✗ {config['name']}: 未找到", "INFO")
                    fail_count += 1
            except Exception as e:
                self.logger.log(f"  ✗ {config['name']} 提取失败：{e}", "DEBUG")
                fail_count += 1

        self.logger.log(f"成功提取 {success_count} 种产品，失败 {fail_count} 种")
        return all_records


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
