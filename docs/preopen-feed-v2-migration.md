# Preopen Feed v2.0 Migration Guide

更新时间：2026-03-08

## 1. 目标

将导出协议从旧版升级到 v2.0，在不中断下游读取的前提下完成路径与字段切换。

## 2. 目录与环境变量

- 新导出目录：`exports/preopen_feed/<batch_id>/`
- 单批次文件：
  - `events.jsonl`
  - `manifest.json`
  - `_SUCCESS`
- 环境变量：
  - `PREOPEN_EXPORT_ROOT`
  - 示例：`E:\Data-Fin\股东报告\exports\preopen_feed`

说明：若未设置 `PREOPEN_EXPORT_ROOT`，系统默认写入 `exports/preopen_feed`。

## 3. Manifest v2.0 约定

`manifest.json` 必含字段：

- `schema_version`: 固定 `"2.0"`
- `batch_id`
- `record_count`
- `generated_at`（ISO8601 + 时区）

兼容字段（保留）：

- `created_at`（与 `generated_at` 同值，供旧读取方兼容）

## 4. events.jsonl 字段约定

兼容期内保留旧字段（至少 2 周）：

- `source_id`
- `event_type`
- `ingested_at`

新增/强化字段：

- `collected_at`（新增）
- `published_at`、`collected_at`、`ingested_at` 统一为 ISO8601 + 时区（示例：`2026-03-08T09:30:00+08:00`）

## 5. 兼容窗口与收敛计划

- 兼容开始：2026-03-08
- 兼容结束（最早）：2026-03-22

在 2026-03-22 之前，不删除旧字段。  
2026-03-22 后再与下游确认字段收敛时间点。

## 6. 下游切换步骤

1. 修改下游环境变量 `PREOPEN_EXPORT_ROOT` 指向 `.../exports/preopen_feed`。
2. 下游先按“双字段兼容”读取（新字段 + 旧字段）。
3. 验证新批次：
   - `_SUCCESS` 存在
   - `manifest.schema_version == "2.0"`
   - `record_count` 与 `events.jsonl` 行数一致
4. 观察稳定后，再计划删除旧字段依赖。

## 7. 回滚方案

若下游读取异常：

1. 保持兼容字段读取不变（优先读取旧字段）。
2. 暂不推进字段收敛。
3. 导出侧可继续写 v2.0，不影响旧字段消费。
