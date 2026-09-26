# SIGNAL 📡 — Source Connector Guide & Architecture

This document describes the design, implementation, and lifecycle of **Source Connectors** in the SIGNAL opportunity intelligence engine.

---

## 1. Overview & Principles

Source Connectors are modular adapters responsible for fetching, parsing, and normalizing announcements, challenges, and opportunities from internet sources into standardized `RawItem` records.

### Core Principles
1. **Lightweight & Headless-Free**: We prioritize structured REST APIs, RSS/Atom syndication feeds, and targeted HTML markup over heavy headless browsers (Playwright/Selenium) or bloated scraping frameworks.
2. **Deterministic Pre-Filtering**: Fast regex-based pre-filtering filters out non-opportunities before invoking LLMs, preventing unnecessary AI cost and rate limit exhaustion.
3. **Traceable Audit Pipeline**: Every fetched item is logged into the `raw_discoveries` table before processing, enabling debugging, auditability, and historical reprocessing.
4. **Idempotent Ingestion**: Repeated connector polls create zero duplicate opportunities and zero database constraint violations using multi-level deduplication (content hash, canonical URL, and title+org matching).

---

## 2. Ingestion Pipeline Lifecycle

```text
    ┌─────────────────────────────────────────────────────────┐
    │                LIVE INTERNET SOURCE                     │
    │  (REST API / RSS Feed / Targeted HTML Portal)           │
    └────────────────────────────┬────────────────────────────┘
                                 │ HTTP GET (ResilientHTTPClient with backoff)
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │                   CONNECTOR (fetch)                     │
    │  Normalized into RawItem(title, url, content, metadata) │
    └────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │                 RAW DISCOVERY AUDIT                     │
    │  Persisted to `raw_discoveries` with content hash       │
    └────────────────────────────┬────────────────────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   │                           │
          [Hash/URL Exists?]                   │
          YES ──► DUPLICATE (Skip)             │
                                               │
                                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │                FAST FILTER (Deterministic)              │
    │  Keyword matches, positive/negative signals, score      │
    └────────────────────────────┬────────────────────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   │                           │
          [Score < 0.25?]                      │
          YES ──► FILTERED_OUT (Skip)          │
                                               │
                                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │         INTELLIGENCE / EXTRACTION GATEWAY               │
    │  AI Classification & Structured Opportunity Extraction  │
    │  (Deterministic Fallback on Mock / Offline mode)        │
    └────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │               DEDUPLICATION (3 Levels)                  │
    │  Level 1: Content Hash | Level 2: URL | Level 3: Title  │
    └────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │            CANONICAL OPPORTUNITY PERSISTENCE            │
    │  Saved to `opportunities`, `opportunity_events`,        │
    │  `organizations`, and linked back to `raw_discoveries`  │
    └─────────────────────────────────────────────────────────┘
```

---

## 3. Implemented Connectors (Phase 1A)

| Connector | Class Name | Source Type | Category | Endpoint / Source | Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Codeforces** | `CodeforcesConnector` | `SourceType.API` | `COMPETITIVE_PROGRAMMING` | `https://codeforces.com/api/contest.list?gym=false` | Official REST API; parses upcoming & recent finished contests |
| **GitHub Tech Blog** | `GitHubBlogConnector` | `SourceType.RSS` | `MAJOR_COMPANY_PROGRAM` | `https://github.blog/feed/` | RSS 2.0 XML; extracts RFC 2822 dates, categories, HTML-stripped body |
| **Smart India Hackathon** | `SIHConnector` | `SourceType.OFFICIAL_WEBSITE` | `HACKATHON` | `https://sih.gov.in/sih2026PS` | Official portal; regex/HTML extraction of problem statement tables & modals |

---

## 4. Authoring a New Connector

To author a new connector, inherit from `BaseConnector` in `connectors/base_connector.py`:

```python
from typing import List
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

class ExampleConnector(BaseConnector):
    def __init__(self, is_active: bool = True):
        super().__init__(
            name="Example Source",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://example.com",
            is_active=is_active,
        )

    async def health_check(self) -> bool:
        """Verify upstream endpoint responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get("https://example.com/api/health")
                return res.status_code == 200
        except Exception:
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch and return normalized RawItems."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            res = await client.get("https://example.com/api/opportunities")
            data = res.json()

        items = []
        for entry in data.get("items", []):
            items.append(
                RawItem(
                    title=entry["title"],
                    url=entry["url"],
                    content=entry["description"],
                    source_name=self.name,
                    source_identifier=str(entry["id"]),
                    metadata={"raw": entry},
                )
            )
        return items
```

### Connector Registration
1. Export the connector in `connectors/__init__.py`.
2. Register the connector slug in `apps/api/routers/ingestion.py` in `CONNECTOR_REGISTRY`.
3. Add a unit test in `tests/test_live_connectors.py` with mock HTTP responses.

---

## 5. Resilient HTTP Client (`ResilientHTTPClient`)

All live connectors use the shared `ResilientHTTPClient` (`services/ingestion/http_client.py`):
- **User-Agent**: Respectful identifier `SIGNAL-Intelligence-Bot/1.0 (+https://github.com/signal-intelligence/signal; opportunity-monitor)`
- **Timeout**: Strict per-request timeout (10-25s) with connection limits.
- **Retry with Exponential Backoff**: Automatically retries 3 times on HTTP 429, 500, 502, 503, 504 and transient connection drops with `backoff = 1.0s * (2.0 ** attempt)`.

---

## 6. Live Ingestion CLI Execution

To run an on-demand live test against real internet sources:

```bash
python scripts/run_live_ingestion.py
```

Or via REST API:
```bash
# Trigger specific connector
curl -X POST http://localhost:8000/api/v1/ingestion/trigger-live/codeforces
curl -X POST http://localhost:8000/api/v1/ingestion/trigger-live/github-blog
curl -X POST http://localhost:8000/api/v1/ingestion/trigger-live/smart-india-hackathon

# Trigger all live connectors
curl -X POST http://localhost:8000/api/v1/ingestion/trigger-live/all

# Audit discoveries
curl http://localhost:8000/api/v1/discoveries
```
