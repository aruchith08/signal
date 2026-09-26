# SIGNAL 📡 — Automated Scheduler & Polling Architecture

## 1. Overview

SIGNAL monitors official portals, feeds, and APIs on a regular cadenced schedule. The **Scheduler Subsystem** provides automated background polling, dynamic interval calculation via **Polling Policies**, full audit logging via `ScheduledJob`, and a RESTful **Observability & Management API**.

---

## 2. Architecture & Components

```text
FastAPI Application Lifespan
          ↓
  AsyncIOScheduler (Singleton)
          ↓
  Coordinator Job (Runs every 5 minutes)
          ↓
Query Eligible Sources (is_active == True AND scheduler_enabled == True)
          ↓
Calculate Due Sources (monitor_frequency_minutes + PollingPolicy)
          ↓
  poll_source(source_slug)
  ├── Independent AsyncSession
  ├── Create ScheduledJob (status="pending")
  ├── IngestionPipeline.process_connector()
  ├── Update Source health metrics (last_polled_at, consecutive_failures)
  └── Update ScheduledJob (status="success"|"failure", duration_ms, items_discovered)
```

---

## 3. Polling Policies (`PollingPolicy`)

Configured per `Source` via the `polling_policy` column:

| Policy | Enum Value | Effective Interval | Use Case |
| :--- | :--- | :--- | :--- |
| **High Priority** | `high_priority` | 30 minutes | Fast-moving competitions, opening registration portals |
| **Medium Priority** | `medium_priority` | 120 minutes (2h) | Standard company and university job/hackathon portals |
| **Low Priority** | `low_priority` | 360 minutes (6h) | Infrequently updated announcement boards |
| **Archival** | `archival` | 1440 minutes (24h)| Reference sites, historical programs |
| **Adaptive** | `adaptive` | Dynamic | Uses `monitor_frequency_minutes` with exponential backoff if consecutive failures > 3 |

---

## 4. Audit Trail (`ScheduledJob`)

Every execution of a source poll is audited in the `scheduled_jobs` table:
* `source_id`: Foreign key to `sources.id` (CASCADE)
* `started_at` / `finished_at`: Execution timing
* `duration_ms`: Latency in milliseconds
* `status`: `pending`, `success`, `failure`, `skipped`
* `items_discovered` / `items_processed`: Ingestion throughput
* `error_message`: Full error trace if failure occurs

---

## 5. Scheduler Observability REST API

Router prefix: `/api/v1/scheduler` (tagged `Scheduler Observability`)

### 1. `GET /api/v1/scheduler/status`
Returns live scheduler state, active background jobs, and configured source metrics:
```json
{
  "running": true,
  "timezone": "UTC",
  "scheduler_jobs_count": 1,
  "active_jobs": ["source_coordinator"],
  "sources": {
    "total": 12,
    "active": 10,
    "scheduler_enabled": 8,
    "due_for_polling": 2
  },
  "recent_successful_polls_24h": 45,
  "recent_failed_polls_24h": 1
}
```

### 2. `GET /api/v1/scheduler/jobs`
Paginated audit log of executions, ordered newest first (`started_at.desc()`):
* Query Parameters:
  * `page` (default: 1)
  * `page_size` (default: 20, max: 100)
  * `source_slug` (optional filter)
  * `status` (optional filter: `success`, `failure`, `pending`)

### 3. `POST /api/v1/scheduler/poll/{source_slug}`
On-demand execution of an active connector source. Returns execution outcome and creates a `ScheduledJob` record:
```json
{
  "success": true,
  "source_slug": "codeforces-api",
  "source_name": "Codeforces API",
  "job_id": "c1f7b8...",
  "status": "success",
  "items_discovered": 4,
  "items_processed": 4,
  "duration_ms": 1150,
  "error_message": null
}
```

### 4. `POST /api/v1/scheduler/poll-all`
Dispatches on-demand polling runs across all active, scheduler-enabled sources.
