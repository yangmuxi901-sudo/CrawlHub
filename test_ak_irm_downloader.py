#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AKShare 互动平台下载器单元测试
"""

import unittest
import os
import sys
import sqlite3
import shutil
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 导入被测模块
from standalone_ak_irm_downloader import (
    Logger,
    clean_filename,
    clean_html_tags,
    save_qa_file,
    init_database,
    get_last_question_date,
    update_last_question_date,
    DEFAULT_START_DATE,
    fetch_hdy_questions,
    fetch_ehd_questions,
)


class TestLogger(unittest.TestCase):
    """测试 Logger 类"""

    def setUp(self):
        self.test_log_path = os.path.join(BASE_DIR, "data", "test_ak_irm_log.txt")
        self.logger = Logger(self.test_log_path)

    def tearDown(self):
        if os.path.exists(self.test_log_path):
            os.remove(self.test_log_path)

    def test_log_write(self):
        """测试日志写入功能"""
        self.logger.log("测试消息", "INFO")
        with open(self.test_log_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[AK_IRM] [INFO] 测试消息", content)

    def test_log_level(self):
        """测试不同日志级别"""
        self.logger.log("错误消息", "ERROR")
        self.logger.log("警告消息", "WARNING")
        with open(self.test_log_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[AK_IRM] [ERROR] 错误消息", content)
        self.assertIn("[AK_IRM] [WARNING] 警告消息", content)


class TestCleanFilename(unittest.TestCase):
    """测试文件名清洗功能"""

    def test_remove_illegal_chars(self):
        """测试移除非法字符"""
        test_cases = [
            ("test/file.txt", "test_file.txt"),
            ("test\\file.txt", "test_file.txt"),
            ("test:file.txt", "test_file.txt"),
            ("test*file.txt", "test_file.txt"),
            ("test?file.txt", "test_file.txt"),
            ('test"file.txt', "test_file.txt"),
            ("test<file.txt", "test_file.txt"),
            ("test>file.txt", "test_file.txt"),
            ("test|file.txt", "test_file.txt"),
        ]
        for input_str, expected in test_cases:
            result = clean_filename(input_str)
            self.assertNotIn("\\", result)
            self.assertNotIn("/", result)
            self.assertNotIn(":", result)
            self.assertNotIn("*", result)
            self.assertNotIn("?", result)
            self.assertNotIn('"', result)
            self.assertNotIn("<", result)
            self.assertNotIn(">", result)
            self.assertNotIn("|", result)

    def test_trim_whitespace(self):
        """测试移除多余空格"""
        self.assertEqual(clean_filename("  test  file  "), "test file")

    def test_length_limit(self):
        """测试长度限制"""
        long_string = "a" * 200
        result = clean_filename(long_string)
        self.assertLessEqual(len(result), 100)


class TestCleanHtmlTags(unittest.TestCase):
    """测试 HTML 标签清理功能"""

    def test_remove_em_tag(self):
        """测试移除 em 标签"""
        self.assertEqual(
            clean_html_tags("这是<em>测试</em>文本"),
            "这是测试文本"
        )

    def test_remove_br_tag(self):
        """测试移除 br 标签"""
        self.assertEqual(
            clean_html_tags("第一行<br>第二行"),
            "第一行第二行"
        )

    def test_remove_multiple_tags(self):
        """测试移除多个标签"""
        html = "<p><em>测试</em>文本</p>"
        result = clean_html_tags(html)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

    def test_nan_input(self):
        """测试 NaN 输入"""
        result = clean_html_tags(pd.NaT)
        self.assertEqual(result, "")


class TestSaveQaFile(unittest.TestCase):
    """测试问答文件保存功能"""

    def setUp(self):
        self.test_dir = os.path.join(BASE_DIR, "data", "test_ak_irm_qa")
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = os.path.join(self.test_dir, "test.txt")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_file_hdy(self):
        """测试保存互动易文件"""
        question = "公司 2026 年的发展战略是什么？"
        answer = "公司将继续专注于主营业务..."
        publish_date = "2026-02-20"

        result = save_qa_file(self.test_file, question, answer, publish_date, "hdy")
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))

    def test_save_file_ehd(self):
        """测试保存 e 互动文件"""
        question = "公司 2026 年的经营计划是什么？"
        answer = "公司将继续聚焦主业..."
        publish_date = "2026-02-20"

        result = save_qa_file(self.test_file, question, answer, publish_date, "ehd")
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))

    def test_file_content_hdy(self):
        """测试互动易文件内容格式"""
        question = "测试问题"
        answer = "测试回答"
        publish_date = "2026-02-20"

        save_qa_file(self.test_file, question, answer, publish_date, "hdy")

        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("互动易投资者问答记录", content)
        self.assertIn(publish_date, content)
        self.assertIn(question, content)
        self.assertIn(answer, content)

    def test_file_content_ehd(self):
        """测试 e 互动文件内容格式"""
        question = "测试问题"
        answer = "测试回答"
        publish_date = "2026-02-20"

        save_qa_file(self.test_file, question, answer, publish_date, "ehd")

        with open(self.test_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("e 互动投资者问答记录", content)
        self.assertIn(publish_date, content)
        self.assertIn(question, content)
        self.assertIn(answer, content)


class TestDatabaseOperations(unittest.TestCase):
    """测试数据库操作"""

    def setUp(self):
        self.test_db = os.path.join(BASE_DIR, "data", "test_ak_irm_sync_record.db")
        # 创建测试数据库
        conn = sqlite3.connect(self.test_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ak_irm_history (
                ticker TEXT NOT NULL,
                platform TEXT NOT NULL,
                last_question_date TEXT NOT NULL,
                updated_at TEXT,
                PRIMARY KEY (ticker, platform)
            )
        ''')
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_get_default_date(self):
        """测试获取默认日期（新股票）"""
        # 临时修改 DB_PATH
        import standalone_ak_irm_downloader as mod
        orig = mod.DB_PATH
        mod.DB_PATH = self.test_db

        date = get_last_question_date("sz.999999", "hdy")
        self.assertEqual(date, DEFAULT_START_DATE)

        # 恢复
        mod.DB_PATH = orig

    def test_update_and_get_date(self):
        """测试更新和获取日期"""
        ticker = "sz.000001"
        platform = "hdy"
        test_date = "2026-02-21"

        # 临时修改 DB_PATH
        import standalone_ak_irm_downloader as mod
        orig = mod.DB_PATH
        mod.DB_PATH = self.test_db

        # 更新
        update_last_question_date(ticker, platform, test_date)

        # 获取
        retrieved_date = get_last_question_date(ticker, platform)
        self.assertEqual(retrieved_date, test_date)

        # 恢复
        mod.DB_PATH = orig

    def test_multi_platform(self):
        """测试多平台隔离"""
        ticker = "sh.600001"
        hdy_date = "2026-02-20"
        ehd_date = "2026-02-21"

        # 临时修改 DB_PATH
        import standalone_ak_irm_downloader as mod
        orig = mod.DB_PATH
        mod.DB_PATH = self.test_db

        # 更新两个平台的日期
        update_last_question_date(ticker, "hdy", hdy_date)
        update_last_question_date(ticker, "ehd", ehd_date)

        # 验证隔离
        self.assertEqual(get_last_question_date(ticker, "hdy"), hdy_date)
        self.assertEqual(get_last_question_date(ticker, "ehd"), ehd_date)

        # 恢复
        mod.DB_PATH = orig


class TestAkShareFetch(unittest.TestCase):
    """测试 AKShare 数据获取（集成测试）"""

    def test_fetch_hdy_real(self):
        """测试互动易真实 API 调用"""
        df = fetch_hdy_questions("300054", "2024-01-01")
        # 只验证返回类型，不验证数据量（因为数据可能变化）
        self.assertIsInstance(df, pd.DataFrame)

    def test_fetch_ehd_real(self):
        """测试 e 互动真实 API 调用"""
        df = fetch_ehd_questions("600071", "2024-01-01")
        self.assertIsInstance(df, pd.DataFrame)


if __name__ == "__main__":
    print("=" * 60)
    print("AKShare 互动平台下载器单元测试")
    print("=" * 60)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanFilename))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanHtmlTags))
    suite.addTests(loader.loadTestsFromTestCase(TestSaveQaFile))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestAkShareFetch))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出结果
    print("\n" + "=" * 60)
    print(f"测试完成：{result.testsRun} 个测试")
    print(f"成功：{result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    print("=" * 60)
