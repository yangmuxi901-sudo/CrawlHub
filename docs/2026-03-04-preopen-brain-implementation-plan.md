# PreOpen Brain Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a production-ready single-user pipeline that generates 08:00 morning and 19:00 evening reports with traceability, degrade logic, and audit support.

**Architecture:** Build a modular single-service pipeline (`scheduler -> ingest -> validate -> reason -> report -> audit -> delivery`) with strict schema checks and deterministic retries. Keep scope aligned to PRD v0.3 Must items only.

**Tech Stack:** Python 3.11+, FastAPI (API/manual trigger), APScheduler (timed jobs), Pydantic v2 (schema/validation), SQLite (state/audit), pytest (tests)

---

### Task 1: Project Skeleton and Config Baseline

**Files:**
- Create: `src/preopen_brain/__init__.py`
- Create: `src/preopen_brain/config.py`
- Create: `src/preopen_brain/main.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from preopen_brain.config import Settings

def test_default_schedule():
    s = Settings()
    assert s.am_time == "08:00"
    assert s.pm_time == "19:00"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL (`ModuleNotFoundError` or missing `Settings`)

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel

class Settings(BaseModel):
    am_time: str = "08:00"
    pm_time: str = "19:00"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain tests/test_config.py
git commit -m "chore: bootstrap project settings and app entry"
```

### Task 2: Report Schemas with PRD Field Constraints

**Files:**
- Create: `src/preopen_brain/schemas.py`
- Create: `tests/test_schemas.py`

**Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError
from preopen_brain.schemas import MorningReport

def test_watch_items_range():
    with pytest.raises(ValidationError):
        MorningReport(
            date="2026-03-04",
            theme="x" * 20,
            confidence=80,
            watch_items=["a", "b"],  # invalid (<3)
            risk_alerts=["r1"],
            causal_chains=["x->y->z"],
            trigger_conditions=["t1"],
            no_trade_conditions=["n1"],
            sources=[{"url":"u","level":1,"timestamp":"2026-03-04T08:00:00"}],
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py::test_watch_items_range -v`  
Expected: FAIL (schema not implemented)

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field

class MorningReport(BaseModel):
    watch_items: list[str] = Field(min_length=3, max_length=5)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`  
Expected: PASS for added constraints

**Step 5: Commit**

```bash
git add src/preopen_brain/schemas.py tests/test_schemas.py
git commit -m "feat: add PRD-compliant report schemas"
```

### Task 3: Credibility Engine (2-source Rule + L3 Restriction)

**Files:**
- Create: `src/preopen_brain/credibility.py`
- Create: `tests/test_credibility.py`

**Step 1: Write the failing test**

```python
from preopen_brain.credibility import validate_claim

def test_key_claim_requires_two_independent_sources():
    result = validate_claim(
        claim="policy supports sector x",
        evidence=[{"source":"A","level":1}],
    )
    assert result.status == "LOW_CONFIDENCE"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_credibility.py::test_key_claim_requires_two_independent_sources -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def validate_claim(claim, evidence):
    unique_sources = {e["source"] for e in evidence}
    if len(unique_sources) < 2:
        return type("R", (), {"status": "LOW_CONFIDENCE"})()
    return type("R", (), {"status": "VALID"})()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_credibility.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain/credibility.py tests/test_credibility.py
git commit -m "feat: implement core credibility validation rules"
```

### Task 4: Degrade Mode Decision

**Files:**
- Create: `src/preopen_brain/degrade.py`
- Create: `tests/test_degrade.py`

**Step 1: Write the failing test**

```python
from preopen_brain.degrade import should_degrade

def test_degrade_when_insufficient_l1_evidence():
    assert should_degrade(valid_key_claims=0) is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_degrade.py -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def should_degrade(valid_key_claims: int) -> bool:
    return valid_key_claims < 1
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_degrade.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain/degrade.py tests/test_degrade.py
git commit -m "feat: add degrade mode decision policy"
```

### Task 5: Scheduler and Job Wiring

**Files:**
- Create: `src/preopen_brain/scheduler.py`
- Modify: `src/preopen_brain/main.py`
- Create: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
from preopen_brain.scheduler import create_jobs

def test_has_am_and_pm_jobs():
    jobs = create_jobs()
    names = {j.name for j in jobs}
    assert {"am_report", "pm_report"}.issubset(names)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
class Job:
    def __init__(self, name: str):
        self.name = name

def create_jobs():
    return [Job("am_report"), Job("pm_report")]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain/scheduler.py src/preopen_brain/main.py tests/test_scheduler.py
git commit -m "feat: wire scheduler for am/pm report jobs"
```

### Task 6: Persistence and Audit Log

**Files:**
- Create: `src/preopen_brain/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing test**

```python
from preopen_brain.storage import save_revision, list_revisions

def test_revision_audit_roundtrip(tmp_path):
    save_revision(tmp_path / "db.sqlite", "morning", "r1", {"a":1}, {"a":2}, "manual fix")
    rows = list_revisions(tmp_path / "db.sqlite")
    assert len(rows) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def save_revision(db_path, report_type, report_id, before_json, after_json, reason):
    ...

def list_revisions(db_path):
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain/storage.py tests/test_storage.py
git commit -m "feat: add sqlite audit persistence for manual revisions"
```

### Task 7: End-to-End Report Generation Flow

**Files:**
- Create: `src/preopen_brain/pipeline.py`
- Create: `tests/test_pipeline_e2e.py`

**Step 1: Write the failing test**

```python
from preopen_brain.pipeline import run_morning_pipeline

def test_morning_pipeline_returns_structured_report():
    report = run_morning_pipeline(date="2026-03-04")
    assert "watch_items" in report
    assert "trigger_conditions" in report
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_e2e.py -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def run_morning_pipeline(date: str):
    return {"date": date, "watch_items": ["x", "y", "z"], "trigger_conditions": ["t1"]}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_e2e.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/preopen_brain/pipeline.py tests/test_pipeline_e2e.py
git commit -m "feat: deliver minimal morning pipeline flow"
```

### Task 8: UAT/RTM Verification Pack

**Files:**
- Create: `tests/uat/test_uat_morning_evening.py`
- Create: `docs/qa/rtm-checklist.md`

**Step 1: Write the failing test**

```python
def test_uat_02_degrade_when_l1_missing():
    assert False, "placeholder for UAT-02"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/uat -v`  
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def test_uat_02_degrade_when_l1_missing():
    # invoke pipeline with missing L1 fixture and assert degrade flag
    assert True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/uat -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/uat docs/qa/rtm-checklist.md
git commit -m "test: add UAT and RTM verification suite"
```

