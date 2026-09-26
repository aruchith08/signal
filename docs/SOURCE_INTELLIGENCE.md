# SIGNAL 📡 — Source Intelligence Architecture

## 1. Overview

SIGNAL's **Source Intelligence System** transforms raw, disconnected internet sources into structured, observable, and continuous opportunity intelligence. Rather than relying on fragile, one-off web scrapers, SIGNAL provides a standardized framework where every source conforms to strict contracts, historical snapshots, semantic diffing, and health telemetry.

---

## 2. End-to-End Pipeline

```text
INTERNET SOURCES (REST API / GraphQL / RSS / JSON Feed / HTML)
        ↓
SOURCE REGISTRY (services/sources/registry.py)
        ↓
CONNECTOR LAYER (connectors/* - Following BaseConnector Contract)
        ↓
FETCH & NORMALIZATION (RawItem + Provenance Metadata)
        ↓
SNAPSHOT PERSISTENCE (SourceSnapshot in database)
        ↓
SEMANTIC & MEANINGFUL CHANGE DETECTION (services/ingestion/change_detection.py)
   ├── No Change / Cosmetic Change ➔ Stamped in Snapshot ➔ Suppressed
   └── Meaningful Change (Status / Date / Item count / Content)
            ↓
DATE EXTRACTION & DEADLINE INTELLIGENCE (services/intelligence/date_extraction.py)
   ├── Later Date ➔ DEADLINE_EXTENDED Event
   ├── Earlier Date ➔ DEADLINE_SHORTENED Event
   └── First Appearance ➔ DEADLINE_ANNOUNCED Event
        ↓
RAW DISCOVERY (Database: raw_discoveries)
        ↓
DOMAIN CLASSIFICATION (Content Understanding)
        ↓
PROGRAM WATCH ENGINE (Monitored Flagship Programs)
        ↓
ENTITY RESOLVER (Integrated with OrganizationAlias)
        ↓
LIFECYCLE ENGINE (State Machine & Event Timeline)
        ↓
CANONICAL OPPORTUNITY & OPPORTUNITY EVENTS
```

---

## 3. Core Components

### A. Source Catalog & Registry (`services/sources/registry.py`)
Centralizes metadata for all monitored sources:
- `SourceDefinition`: Declarative definition containing slug, organization, category, source type, connector class, polling frequency, and trust tier.
- `SourceRegistry`: Lookup and filtering service by category, priority, and enabled state. Provides connector instantiation.

### B. Connector Architecture (`connectors/base_connector.py`)
All connectors inherit from `BaseConnector` and return normalized `RawItem` instances:
- `title`: Sanitized human-readable title.
- `url`: Official destination link.
- `content`: Extracted text content.
- `source_name`: Standardized source identifier.
- `source_identifier`: Unique external ID (e.g. `codechef-START150`).
- `published_at`: Timezone-aware UTC timestamp.
- `metadata`: Connector-specific attributes, timings, and extraction methods.

### C. Source Snapshot System (`apps/api/models/snapshot.py`)
Every connector run records a point-in-time `SourceSnapshot`:
- `snapshot_hash`: SHA256 of cleaned, noise-free normalized content.
- `content_hash`: SHA256 of raw response payload.
- `normalized_content`: Collapsed, lowercase text for structural diffing.
- `items_count`: Count of items discovered.
- `change_type`: State classification (`NO_CHANGE`, `CONTENT_CHANGED`, `NEW_ITEM`, `ITEM_REMOVED`, `DEADLINE_CHANGED`, `STATUS_CHANGED`).

### D. Connector Health Telemetry (`apps/api/models/source.py`)
Each `Source` record automatically tracks operational health:
- `consecutive_failures`: Incremented on errors; reset to 0 on success.
- `average_response_time`: Exponential rolling average response time (ms).
- `last_error`: Traceback snippet or error description.
- `status`:
  - `HEALTHY`: `consecutive_failures < 3`
  - `DEGRADED`: `3 <= consecutive_failures < 5`
  - `FAILING`: `consecutive_failures >= 5`
  - `DISABLED`: Manually disabled by operator.

### E. Polling Policies (`shared/constants.py`)
Sources are categorized into polling policy tiers:
- `HIGH_PRIORITY`: Monitored every 30 minutes (e.g. Codeforces, CodeChef, SIH).
- `MEDIUM_PRIORITY`: Monitored every 2 hours (e.g. MyGov Innovate, MLH).
- `LOW_PRIORITY`: Monitored every 6 hours (e.g. GitHub Blog).
- `ARCHIVAL`: Monitored once per day.

---

## 4. Operational Commands

### Poll Specific Source:
```bash
python scripts/poll_sources.py --source codechef
```

### Poll by Priority Tier:
```bash
python scripts/poll_sources.py --priority critical
```

### Seed Organization Aliases:
```bash
python scripts/seed_organization_aliases.py
```
