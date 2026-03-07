# Domestic News Aggregator Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate domestic news aggregation (Juhe + TianAPI) into the existing crawler platform as scheduled, configurable, and low-maintenance data sources.

**Architecture:** Add a unified crawler module that normalizes Juhe/TianAPI responses into existing `finance_news` schema, then wire it into `scheduler_service.py` and `config/scheduler.yaml` as opt-in jobs. Keep backward compatibility by defaulting jobs to disabled and requiring API keys via env vars.

**Tech Stack:** Python 3.x, requests, sqlite3, APScheduler, YAML

---

### Task 1: Define and lock integration scope

**Files:**
- Modify: `docs/plans/2026-03-07-domestic-news-aggregator-integration-plan.md`
- Reference: `scheduler_service.py`, `config/scheduler.yaml`, `web/api.py`

**Step 1: Validate required behavior list**
- Confirm only three changes in this iteration:
1. New crawler (`Juhe + TianAPI`)
2. Scheduler job registration
3. Dashboard job visibility

**Step 2: Lock non-goals**
- No exporter changes
- No schema migration
- No replacement of existing source crawlers in this iteration

**Step 3: Commit planning baseline**
Run:
```bash
git add docs/plans/2026-03-07-domestic-news-aggregator-integration-plan.md
git commit -m "docs: add domestic aggregator integration plan"
```

### Task 2: Add crawler tests first (TDD)

**Files:**
- Create: `tests/test_news_domestic_aggregator.py`
- Test: `tests/test_news_domestic_aggregator.py`

**Step 1: Write failing tests for normalization and missing-key behavior**
- `test_fetch_juhe_without_key_returns_empty`
- `test_fetch_tianapi_without_key_returns_empty`
- `test_save_news_inserts_unique_links`

**Step 2: Run tests to verify FAIL**
Run:
```bash
pytest tests/test_news_domestic_aggregator.py -v
```
Expected: FAIL (module/function missing or behavior mismatch)

**Step 3: Commit test scaffolding**
Run:
```bash
git add tests/test_news_domestic_aggregator.py
git commit -m "test: add domestic aggregator crawler tests"
```

### Task 3: Implement unified domestic aggregator crawler

**Files:**
- Create/Modify: `crawlers/news_domestic_aggregator.py`
- Reference: `crawlers/news_cls.py`, `crawlers/news_yicai.py`

**Step 1: Implement minimal crawler class**
- Class: `DomesticAggregatorCrawler(BaseCrawler)`
- Methods:
  - `init_db()`
  - `_fetch_juhe()`
  - `_fetch_tianapi()`
  - `save_news()`
  - `crawl(provider='all', pages=1, page_size=30)`

**Step 2: Ensure normalization contract**
- Output into `finance_news` fields:
  - `title`, `source`, `pub_date`, `link`, `article`
- Dedup based on `UNIQUE(link)` + `INSERT OR IGNORE`

**Step 3: Run tests to verify PASS**
Run:
```bash
pytest tests/test_news_domestic_aggregator.py -v
```
Expected: PASS

**Step 4: Commit crawler implementation**
Run:
```bash
git add crawlers/news_domestic_aggregator.py
git commit -m "feat: add domestic news aggregator crawler for juhe and tianapi"
```

### Task 4: Wire scheduler jobs and runtime entrypoints

**Files:**
- Modify: `scheduler_service.py`
- Modify: `config/scheduler.yaml`

**Step 1: Add run wrappers in scheduler**
- `run_news_juhe_domestic()`
- `run_news_tianapi_domestic()`

**Step 2: Register jobs in `JOB_REGISTRY`**
- `news_juhe_domestic`
- `news_tianapi_domestic`

**Step 3: Add cron config entries (disabled by default)**
- Add both jobs with clear comments:
  - require `JUHE_API_KEY`
  - require `TIANAPI_API_KEY`

**Step 4: Run smoke checks**
Run:
```bash
python scheduler_service.py --run-now news_juhe_domestic
python scheduler_service.py --run-now news_tianapi_domestic
```
Expected: no crash; returns 0 when key missing; logs warning

**Step 5: Commit scheduler integration**
Run:
```bash
git add scheduler_service.py config/scheduler.yaml
git commit -m "feat: add schedulable domestic news aggregator jobs"
```

### Task 5: Update dashboard/API job visibility

**Files:**
- Modify: `web/api.py`

**Step 1: Add job metadata in `get_jobs()`**
- `news_juhe_domestic`
- `news_tianapi_domestic`

**Step 2: Validate API response includes new jobs**
Run:
```bash
python web/api.py --port 8080
# separate shell
curl http://localhost:8080/api/jobs
```
Expected: two new jobs appear in response

**Step 3: Commit dashboard metadata update**
Run:
```bash
git add web/api.py
git commit -m "feat: expose domestic aggregator jobs in dashboard api"
```

### Task 6: Documentation and operator runbook

**Files:**
- Modify: `README.md`
- Create: `docs/ops/domestic-aggregator-env.md`

**Step 1: Document env vars and startup flow**
- `JUHE_API_KEY`
- `TIANAPI_API_KEY`
- Optional URLs/types

**Step 2: Add “quick start” commands**
```bash
python scheduler_service.py --run-now news_juhe_domestic
python scheduler_service.py --run-now news_tianapi_domestic
```

**Step 3: Commit docs**
Run:
```bash
git add README.md docs/ops/domestic-aggregator-env.md
git commit -m "docs: add domestic aggregator setup and runbook"
```

### Task 7: Final verification and delivery

**Files:**
- Verify: `data/sync_record.db` (runtime only, no commit)

**Step 1: Run focused checks**
Run:
```bash
pytest -q
python scheduler_service.py --run-now news_juhe_domestic
python scheduler_service.py --run-now news_tianapi_domestic
```

**Step 2: Validate result rows (manual SQL)**
```sql
SELECT source, COUNT(*) FROM finance_news
WHERE source IN ('聚合-Juhe', '聚合-TianAPI')
GROUP BY source;
```

**Step 3: Prepare handoff summary**
- Changed files
- How to enable jobs
- Known caveats (API quota, key missing)

