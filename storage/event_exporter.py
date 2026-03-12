#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
事件导出器 - 金融新闻数据聚合器
导出格式：JSONL + manifest.json + _SUCCESS
支持 watermark 机制、幂等性保证、checksum 校验
"""

import os
import sys
import json
import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from pathlib import Path

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_EXPORTS_DIR = os.path.join(BASE_DIR, "exports", "preopen_feed")
DB_PATH = os.path.join(DATA_DIR, "sync_record.db")
EXPORT_TZ = timezone(timedelta(hours=8))
CORE_MAX_SOURCE_LEVEL = 2

# 数据源可信级别（数字越小可信度越高）
SOURCE_LEVELS = {
    # L1
    "国家统计局": 1,
    "中国人民银行": 1,
    "央视新闻": 1,
    "央视新闻客户端": 1,
    # L2
    "财联社": 2,
    "财联社深度": 2,
    "第一财经": 2,
    "证券时报": 2,
    "上海证券报": 2,
    "搜狐财经": 2,
    "港交所": 2,
}


def resolve_export_root() -> str:
    """解析导出根目录，支持 PREOPEN_EXPORT_ROOT 覆盖"""
    root = os.getenv("PREOPEN_EXPORT_ROOT", "").strip()
    if not root:
        root = DEFAULT_EXPORTS_DIR
    elif not os.path.isabs(root):
        root = os.path.join(BASE_DIR, root)
    os.makedirs(root, exist_ok=True)
    return root


class WatermarkManager:
    """Watermark 管理器 - 生产位点和消费位点"""

    def __init__(self):
        self.watermark_dir = os.path.join(DATA_DIR, "watermarks")
        os.makedirs(self.watermark_dir, exist_ok=True)
        self.producer_watermark_file = os.path.join(self.watermark_dir, "producer_watermark.json")
        self.consumer_watermark_dir = os.path.join(self.watermark_dir, "consumers")
        os.makedirs(self.consumer_watermark_dir, exist_ok=True)

    def get_producer_watermark(self, source: str = None) -> Dict:
        """获取生产位点"""
        if os.path.exists(self.producer_watermark_file):
            with open(self.producer_watermark_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if source:
                    return data.get(source, {"last_event_id": None, "last_published_at": None})
                return data
        return {}

    def update_producer_watermark(self, source: str, event_id: str, published_at: str):
        """更新生产位点"""
        data = self.get_producer_watermark()
        data[source] = {
            "last_event_id": event_id,
            "last_published_at": published_at,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(self.producer_watermark_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_consumer_watermark(self, consumer_id: str) -> Dict:
        """获取消费位点"""
        consumer_file = os.path.join(self.consumer_watermark_dir, f"{consumer_id}.json")
        if os.path.exists(consumer_file):
            with open(consumer_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"last_consumed_event_id": None, "last_consumed_at": None}

    def update_consumer_watermark(self, consumer_id: str, event_id: str, consumed_at: str):
        """更新消费位点"""
        consumer_file = os.path.join(self.consumer_watermark_dir, f"{consumer_id}.json")
        data = {
            "last_consumed_event_id": event_id,
            "last_consumed_at": consumed_at,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(consumer_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class EventExporter:
    """事件导出器"""

    # 必填字段
    REQUIRED_FIELDS = [
        'event_id', 'source', 'source_id', 'title',
        'published_at', 'url', 'event_type', 'ingested_at'
    ]

    def __init__(self, batch_id: str = None):
        self.batch_id = batch_id or self._generate_batch_id()
        self.export_root = resolve_export_root()
        self.export_dir = os.path.join(self.export_root, self.batch_id)
        self.events_file = os.path.join(self.export_dir, "events.jsonl")
        self.manifest_file = os.path.join(self.export_dir, "manifest.json")
        self.success_file = os.path.join(self.export_dir, "_SUCCESS")
        self.watermark_mgr = WatermarkManager()
        self.events = []
        self.rejected_events = []
        self.exported_event_ids = set()  # 用于幂等性检查

    def _generate_batch_id(self) -> str:
        """生成批次 ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _generate_event_id(self, source: str, source_id: str, url: str) -> str:
        """生成事件唯一 ID（基于内容哈希，保证幂等性）"""
        content = f"{source}:{source_id}:{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _now_iso(self) -> str:
        """当前时间（ISO8601 +08:00）"""
        return datetime.now(EXPORT_TZ).isoformat(timespec="seconds")

    def _format_timestamp(self, ts_str: str) -> str:
        """格式化时间戳为 ISO8601 + 时区"""
        if not ts_str:
            return self._now_iso()

        raw = str(ts_str).strip()
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = None

        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(raw[:19], fmt)
                    break
                except ValueError:
                    continue

        if dt is None:
            return self._now_iso()

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=EXPORT_TZ)
        else:
            dt = dt.astimezone(EXPORT_TZ)

        return dt.isoformat(timespec="seconds")

    def _classify_source_level(self, source: str) -> int:
        """返回数据源分级，未知源默认 L3"""
        return int(SOURCE_LEVELS.get(source or "", 3))

    def _admission_decision(self, source: str) -> tuple[int, str, str]:
        """源头准入：仅 L1/L2 进入主流，L3 进隔离"""
        level = self._classify_source_level(source)
        if level <= CORE_MAX_SOURCE_LEVEL:
            return level, "accepted", ""
        return level, "rejected", "source_level_l3_restricted"

    def fetch_events_from_db(self, source_filter: str = None, watermark_filter: Dict = None) -> List[Dict]:
        """从数据库获取事件"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 查询新闻数据
        if source_filter:
            cursor.execute("""
                SELECT id, source, title, pub_date, link, article, category
                FROM finance_news
                WHERE source = ?
                ORDER BY pub_date DESC
                LIMIT 1000
            """, (source_filter,))
        else:
            cursor.execute("""
                SELECT id, source, title, pub_date, link, article, category
                FROM finance_news
                ORDER BY pub_date DESC
                LIMIT 1000
            """)

        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            db_id, source, title, pub_date, link, article, category = row

            # 幂等性检查：如果事件已导出，跳过
            event_id = self._generate_event_id(source, str(db_id), link)
            if event_id in self.exported_event_ids:
                continue

            # 应用 watermark 过滤
            if watermark_filter:
                last_event_id = watermark_filter.get("last_event_id")
                last_published_at = watermark_filter.get("last_published_at")
                if last_event_id and event_id <= last_event_id:
                    continue

            now_iso = self._now_iso()
            source_level, admission_status, reject_reason = self._admission_decision(source)
            event = {
                "event_id": event_id,
                "source": source or "unknown",
                "source_level": source_level,
                "admission_status": admission_status,
                "reject_reason": reject_reason,
                "source_id": str(db_id),
                "title": title or "",
                "published_at": self._format_timestamp(pub_date) if pub_date else None,
                "url": link or "",
                "event_type": category or "news",
                "ingested_at": now_iso,
                "collected_at": now_iso,
                "content": article[:2000] if article else None,
            }

            # L3 隔离：不进入主事件流，但保留审计记录
            if admission_status != "accepted":
                self.rejected_events.append(event)
                continue

            # 必填字段检查
            if all(event.get(f) for f in self.REQUIRED_FIELDS[:6]):  # 前 6 个必填
                events.append(event)
                self.exported_event_ids.add(event_id)

                # 更新生产位点
                self.watermark_mgr.update_producer_watermark(
                    source, event_id, event["published_at"]
                )

        return events

    def add_events(self, events: List[Dict]):
        """添加事件到导出列表"""
        self.events.extend(events)

    def write_events_file(self) -> int:
        """写入 events.jsonl 文件"""
        os.makedirs(self.export_dir, exist_ok=True)

        with open(self.events_file, 'w', encoding='utf-8') as f:
            for event in self.events:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')

        return len(self.events)

    def compute_checksum(self, file_path: str) -> str:
        """计算文件 SHA256 校验和"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def count_lines(self, file_path: str) -> int:
        """计算文件行数"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)

    def write_manifest(self, record_count: int) -> Dict:
        """写入 manifest.json 文件"""
        checksum = self.compute_checksum(self.events_file)
        generated_at = self._now_iso()
        rejected_reason_stats = {}
        for item in self.rejected_events:
            reason = item.get("reject_reason", "") or "unknown"
            rejected_reason_stats[reason] = rejected_reason_stats.get(reason, 0) + 1

        manifest = {
            "batch_id": self.batch_id,
            "generated_at": generated_at,
            "created_at": generated_at,  # 兼容旧字段
            "record_count": record_count,
            "accepted_count": record_count,
            "rejected_count": len(self.rejected_events),
            "reject_reason_stats": rejected_reason_stats,
            "files": {
                "events": "events.jsonl",
            },
            "checksum": {
                "events.jsonl": checksum,
            },
            "schema_version": "2.0",
            "schema": {
                "required_fields": self.REQUIRED_FIELDS,
                "optional_fields": [
                    "content",
                    "category",
                    "tickers",
                    "sentiment",
                    "collected_at",
                    "source_level",
                    "admission_status",
                    "reject_reason",
                ],
                "legacy_compat_fields": ["source_id", "event_type", "ingested_at"],
            },
            "watermark": self.watermark_mgr.get_producer_watermark(),
        }

        with open(self.manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest

    def write_success_marker(self):
        """写入 _SUCCESS 标志文件"""
        with open(self.success_file, 'w', encoding='utf-8') as f:
            f.write(f"Export completed at {datetime.now(timezone.utc).isoformat()}\n")

    def validate_manifest(self) -> Dict:
        """校验 manifest 与实际文件是否一致"""
        with open(self.manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        # 校验记录数
        actual_count = self.count_lines(self.events_file)
        expected_count = manifest.get("record_count", 0)

        # 校验 checksum
        actual_checksum = self.compute_checksum(self.events_file)
        expected_checksum = manifest.get("checksum", {}).get("events.jsonl", "")

        return {
            "record_count_match": actual_count == expected_count,
            "checksum_match": actual_checksum == expected_checksum,
            "actual_count": actual_count,
            "expected_count": expected_count,
            "actual_checksum": actual_checksum,
            "expected_checksum": expected_checksum,
        }

    def export(self, source_filter: str = None) -> Dict:
        """
        执行导出流程

        Returns:
            导出结果摘要
        """
        print(f"[{self.batch_id}] 开始导出...")

        # 1. 从数据库获取事件
        events = self.fetch_events_from_db(source_filter)
        print(f"[{self.batch_id}] 获取到 {len(events)} 条事件")

        if not events:
            print(f"[{self.batch_id}] 无事件可导出")
            return {"status": "empty", "batch_id": self.batch_id}

        # 2. 添加事件
        self.add_events(events)

        # 3. 写入 events.jsonl
        record_count = self.write_events_file()
        print(f"[{self.batch_id}] 已写入 {record_count} 条记录到 events.jsonl")

        # 4. 写入 manifest.json
        manifest = self.write_manifest(record_count)
        print(f"[{self.batch_id}] 已写入 manifest.json")

        # 5. 写入 _SUCCESS 标志
        self.write_success_marker()
        print(f"[{self.batch_id}] 已写入 _SUCCESS 标志")

        # 6. 校验 manifest
        validation = self.validate_manifest()
        print(f"[{self.batch_id}] 校验结果：记录数={validation['record_count_match']}, checksum={validation['checksum_match']}")

        return {
            "status": "success",
            "batch_id": self.batch_id,
            "export_dir": self.export_dir,
            "record_count": record_count,
            "manifest": manifest,
            "validation": validation,
        }


def export_batch(source: str = None, batch_id: str = None) -> Dict:
    """
    执行单批次导出

    Args:
        source: 指定数据源，None 表示全部
        batch_id: 指定批次 ID，None 表示自动生成

    Returns:
        导出结果
    """
    exporter = EventExporter(batch_id)
    return exporter.export(source)


def list_exports(limit: int = 10) -> List[Dict]:
    """列出最近的导出批次"""
    export_root = resolve_export_root()
    exports = []
    for name in sorted(os.listdir(export_root), reverse=True):
        batch_dir = os.path.join(export_root, name)
        if os.path.isdir(batch_dir):
            success_file = os.path.join(batch_dir, "_SUCCESS")
            manifest_file = os.path.join(batch_dir, "manifest.json")

            batch_info = {
                "batch_id": name,
                "has_success": os.path.exists(success_file),
                "has_manifest": os.path.exists(manifest_file),
            }

            if os.path.exists(manifest_file):
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    batch_info["record_count"] = manifest.get("record_count", 0)
                    batch_info["created_at"] = manifest.get("generated_at", manifest.get("created_at", ""))

            exports.append(batch_info)

            if len(exports) >= limit:
                break

    return exports


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="金融新闻事件导出器")
    parser.add_argument("--source", type=str, help="指定数据源")
    parser.add_argument("--batch-id", type=str, help="指定批次 ID")
    parser.add_argument("--list", action="store_true", help="列出最近的导出批次")

    args = parser.parse_args()

    if args.list:
        exports = list_exports()
        print(f"\n最近的导出批次（最多 10 个）:\n")
        for exp in exports:
            status = "✅" if exp.get("has_success") else "❌"
            print(f"{status} {exp['batch_id']}: {exp.get('record_count', 0)} 条记录")
            print(f"   创建时间：{exp.get('created_at', 'N/A')}")
        return

    result = export_batch(args.source, args.batch_id)
    print(f"\n导出完成:")
    print(f"  状态：{result.get('status')}")
    print(f"  批次：{result.get('batch_id')}")
    print(f"  记录数：{result.get('record_count', 0)}")
    print(f"  目录：{result.get('export_dir', 'N/A')}")


if __name__ == "__main__":
    main()
