# THS + Sina Priority Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add high-relevance domestic sources (同花顺 + 新浪财经) as first-class inputs and keep existing high-value公告抽取链路, then feed unified exporter.

**Architecture:** Keep `finance_news` + `exchange_announcements` schema unchanged. Add two source crawlers (`news_sina_finance.py`, `news_ths_finance.py`) with正文抽取 and source-specific分类. Wire jobs into scheduler + dashboard with conservative defaults (`enabled: false`).

**Tech Stack:** Python requests + lxml, sqlite3, APScheduler, existing BaseCrawler

---

### Task 1: Scope and compatibility lock

**Files:**
- Modify: `docs/plans/2026-03-07-ths-sina-priority-integration-plan.md`
- Reference: `crawlers/cninfo_announcement.py`, `crawlers/news_hkex.py`, `storage/event_exporter.py`

**Step 1: Lock source priority**
1. 同花顺财经（高优先）
2. 新浪财经（高优先）
3. 聚合源（Juhe/TianAPI）仅补充

**Step 2: Lock non-breaking constraints**
- No table migration in this iteration
- Exporter contract unchanged
- Existing公告抽取保留（CNINFO/HKEX）

### Task 2: Test-first for new crawlers

**Files:**
- Create: `test_news_sina_finance.py`
- Create: `test_news_ths_finance.py`

**Step 1: Write failing tests**
- List parsing -> title/link/pub_date extraction
- Detail extraction -> article正文 extraction
- save_news dedup -> unique(link)

**Step 2: Run and confirm fail**
```bash
pytest -q test_news_sina_finance.py test_news_ths_finance.py
```

### Task 3: Implement Sina crawler

**Files:**
- Create: `crawlers/news_sina_finance.py`

**Step 1: Implement list fetch + parse**
- 支持财经主列表/快讯列表
- 解析标题、链接、发布时间

**Step 2: Implement detail正文抽取**
- 文章页正文选择器优先级
- 清理模板噪音

**Step 3: Persist to finance_news**
- source=`新浪财经`
- category=`财经`/`快讯`（按路由映射）

### Task 4: Implement THS crawler

**Files:**
- Create: `crawlers/news_ths_finance.py`

**Step 1: Implement list fetch + parse**
- 同花顺财经频道列表
- 解析标题、链接、发布时间

**Step 2: Implement detail正文抽取**
- 正文选择器 + 降级提取

**Step 3: Persist to finance_news**
- source=`同花顺财经`
- category按频道映射

### Task 5: Scheduler + Dashboard wiring

**Files:**
- Modify: `scheduler_service.py`
- Modify: `config/scheduler.yaml`
- Modify: `web/api.py`

**Step 1: Register jobs**
- `news_sina_finance`
- `news_ths_finance`

**Step 2: Add config entries (disabled by default)**
- 建议时段：交易日 9-17 点，15~20 分钟

**Step 3: Add dashboard labels**
- “新浪财经”
- “同花顺财经”

### Task 6: Relevance and output tuning

**Files:**
- Modify: `storage/event_exporter.py` (if needed)
- Modify: `docs/ops/*.md`

**Step 1: Add source priority note**
- Exporter优先保留高相关来源字段

**Step 2: Define report-side filtering guidance**
- 将“公告/监管/公司事件”作为高优先事件类型

### Task 7: Verification and handoff

**Files:**
- Create: `docs/ops/2026-03-07-ths-sina-smoke-report.md`

**Step 1: Run smoke jobs**
```bash
python scheduler_service.py --run-now news_sina_finance
python scheduler_service.py --run-now news_ths_finance
```

**Step 2: SQL validation**
```sql
SELECT source, COUNT(*), MAX(pub_date)
FROM finance_news
WHERE source IN ('新浪财经', '同花顺财经')
GROUP BY source;
```

**Step 3: Export visibility check**
```bash
python storage/event_exporter.py
python storage/event_exporter.py --list
```

