# SIGNAL 📡 — Phase 0.5: Engineering Audit & Architectural Hardening Report

**Date**: September 2026  
**Auditor**: Lead Software Architect & Full-Stack Core Engineering  
**Scope**: Complete Phase 0 codebase audit covering data persistence, ingestion, AI gateway, source connectors, pre-filtering, REST APIs, and test verification.

---

## 1. Executive Summary

Phase 0 established the structural blueprint of SIGNAL. Phase 0.5 critically inspected every component to determine whether the foundation is truly ready to scale from mock data to 10, 50, and 100+ live internet sources without race conditions, false-negative rejections, or unhandled failures.

### Key Outcomes of Phase 0.5:
1. **Alembic Migrations Rescued**: Discovered and resolved an issue where initial migrations were generated as empty `pass` stubs due to pre-existing SQLite database state. Generated a verified, comprehensive DDL migration containing all 9 normalized tables and indexes.
2. **Database Hardening**: Added operational monitoring telemetry (`last_successful_check`, `failure_count`) to `Source`; enforced `unique=True` on `Opportunity.content_hash` and `Opportunity.slug` to guarantee duplicate rejection at the database transaction level.
3. **Robust Change Detection**: Replaced raw string hashing with whitespace-, CRLF-, and line-break normalized hashing, ensuring benign formatting shifts do not trigger false new opportunities.
4. **Multi-Level Deduplication Engine**: Built a standalone `Deduplicator` supporting normalized hash matching, canonical URL normalization (stripping tracking parameters), and title/organization matching, with an explicit architectural extension hook for Phase 3 vector embeddings.
5. **False-Negative Elimination in FastFilter**: Added 14+ missing real-world announcement phrases (*"Applications are open"*, *"Call for applications"*, *"Deadline extended"*, *"Nominations open"*, *"Student challenge"*, *"Entries invited"*) and made filter keywords configurable at runtime.
6. **AI Gateway Timeouts & Telemetry**: Wrapped all external provider invocations with `asyncio.wait_for`, preventing hanging third-party APIs from freezing the pipeline; added latency logging in milliseconds and custom typed exceptions (`AITimeoutError`, `AIProviderError`, `AIResponseValidationError`).

---

## 2. Architecture Status Matrix

| Component | Implementation Status | Implementation Notes |
| :--- | :--- | :--- |
| **FastAPI Core & Routers** | `IMPLEMENTED` | Lifespan events, CORS, OpenAPI documentation, and dual pagination (`page`/`page_size` and `limit`/`offset`) fully functional. |
| **SQLAlchemy 2.0 Async Engine** | `IMPLEMENTED` | Async engine, sessionmaker dependency injection, and clean transaction handling. |
| **PostgreSQL & SQLite Support** | `IMPLEMENTED` | Portable schema; runs on SQLite for development and PostgreSQL 16 via Docker Compose. |
| **Alembic Migrations** | `IMPLEMENTED` | Tested and verified against fresh database: `revision --autogenerate` and `upgrade head` both functional. |
| **Data Models (9 Tables)** | `IMPLEMENTED` | `organizations`, `sources`, `opportunities`, `opportunity_events`, `users`, `user_profiles`, `user_interests`, `notifications`. Foreign keys, cascading deletes, indexes, and unique constraints enforced. |
| **FastFilter** | `IMPLEMENTED` | High-throughput regex pre-filter; hardened against false negatives; configurable positive and negative rule sets. |
| **Change Detection** | `IMPLEMENTED` | SHA-256 hashing on normalized content (CRLF normalized, whitespace collapsed). |
| **Deduplication Engine** | `IMPLEMENTED` (Multi-Level) | Three-level matching: (1) normalized hash, (2) canonical URL, (3) normalized title + org. (Semantic embedding deduplication intentionally postponed to Phase 3). |
| **AI Router & Fallback Chain** | `IMPLEMENTED` | Task-based routing (`classify`, `extract`, `summarize`) with timeout enforcement, typed error isolation, and latency telemetry. |
| **Mock AI Provider** | `IMPLEMENTED` | Deterministic, offline provider used for automated testing and zero-cost local development. |
| **NVIDIA Provider Adapter** | `INTERFACE / STUB` | Structure and exception handling ready; live NIM endpoint calls stubbed pending API keys in Phase 1. |
| **Gemini Provider Adapter** | `INTERFACE / STUB` | Structure and exception handling ready; live Gemini 1.5 Flash/Pro calls stubbed pending API keys in Phase 1. |
| **OpenAI Provider Adapter** | `INTERFACE / STUB` | Structure and exception handling ready; live GPT-4o-mini calls stubbed pending API keys in Phase 1. |
| **Source Connector Interface** | `IMPLEMENTED` | `BaseConnector` defines contract; includes health check, `is_active` check, and canonical URL normalization. |
| **Mock Source Connector** | `IMPLEMENTED` | Yields multi-category announcements (TCS CodeVita, Smart India Hackathon, Flipkart GRiD) for testing. |
| **Telegram Notifier** | `INTERFACE / STUB` | `TelegramNotifier` has live HTTP POST payload formatting via `httpx`, but credentials are unconfigured in Phase 0. |
| **Mock Notifier** | `IMPLEMENTED` | In-memory message store and console logger for alert dispatch testing. |
| **Personalization Engine** | `PARTIALLY IMPLEMENTED` | Data models (`user_interests`, `user_profiles`) exist; algorithmic interest-scoring is planned for Phase 2. |
| **Distributed Task Queue** | `NOT IMPLEMENTED` | Intentionally postponed per prompt guidelines; scheduled polling currently runs directly via async pipeline. |

---

## 3. Findings & Vulnerability Analysis

### [CRITICAL] 1. Alembic Autogenerate Generated Empty Migration
* **Issue**: Autogenerate inspected a database where tables were already created dynamically by `init_db()`. Consequently, Alembic detected zero schema changes and generated an empty `upgrade()` containing only `pass`. Anyone initializing a fresh PostgreSQL database would have had an empty database.
* **Resolution**: Wiped existing dev database, regenerated clean initial DDL migration (`ae04da361e40_initial_tables`), verified full migration creation of all 9 tables and indexes via `alembic upgrade head`.

### [HIGH] 2. Benign Formatting Caused Change Detection Failures
* **Issue**: `compute_content_hash` hashed raw strings directly. Differences in line endings (`\r\n` vs `\n`) or trailing whitespace across scraping passes resulted in different hashes, falsely creating duplicate opportunities.
* **Resolution**: Created `normalize_content_for_hash()` in `shared/utils.py` that normalizes line endings, strips line-level whitespace, and collapses blank lines prior to SHA-256 calculation.

### [HIGH] 3. FastFilter False-Negative Risk
* **Issue**: The initial keyword regex lacked common opportunity headlines such as *"Applications are open"*, *"Call for applications"*, *"Deadline extended"*, *"Nominations open"*, *"Student challenge"*, and *"Entries invited"*. Under real internet scraping, valid announcements would have been discarded before reaching the AI.
* **Resolution**: Added comprehensive real-world phrases to `DEFAULT_POSITIVE_KEYWORDS` in `services/ingestion/filter.py` and added runtime pattern configuration via constructor arguments and `add_positive_pattern()`.

### [HIGH] 4. Lack of Timeout Protection in AI Gateway
* **Issue**: `AIRouter` lacked timeout enforcement (`asyncio.wait_for`). If a third-party API provider experienced network degradation or hung on socket read, the entire ingestion pipeline would hang indefinitely.
* **Resolution**: Added `_execute_with_timeout()` with configurable limits (`default_timeout_seconds=15.0`), raising `AITimeoutError` and triggering automatic fallback to the next provider.

### [MEDIUM] 5. Missing Operational Monitoring Metadata on Sources
* **Issue**: The `Source` entity had no mechanism to record whether a polling attempt succeeded or failed, nor a count of consecutive errors.
* **Resolution**: Added `last_successful_check` and `failure_count` to `Source` model, updated Alembic schema (`ad8ee8a54748`), and updated `IngestionPipeline` to record successes and increment failures.

### [MEDIUM] 6. Duplicate Prevention Lacked Database-Level Enforcements
* **Issue**: `content_hash` and `slug` were indexed but not enforced as `unique=True`. Concurrent worker processes could produce race conditions resulting in duplicate rows.
* **Resolution**: Enforced `unique=True` on `Opportunity.slug` and `Opportunity.content_hash` in SQLAlchemy models and Alembic migrations.

---

## 4. Incomplete Features & Intentional Stubs

To ensure complete transparency before Phase 1:

1. **NVIDIA, Gemini, and OpenAI Providers**:
   * *Current State*: `INTERFACE / STUB`. The classes inherit from `BaseAIProvider`, handle API key presence in `is_available()`, and normalize errors. They do not yet invoke live HTTP endpoints to preserve zero API cost during foundation development.
   * *Phase 1 Action*: Implement live REST payload serialization and JSON schema validation when live API keys are provided.
2. **Telegram Notifier**:
   * *Current State*: `INTERFACE / STUB`. Contains production Markdown formatting and HTTP POST dispatch logic via `httpx`, but is gated on `TELEGRAM_BOT_TOKEN`.
   * *Phase 2 Action*: Connect live Telegram Bot webhook and chat ID routing.
3. **Semantic Embedding Deduplication**:
   * *Current State*: `STUBBED EXTENSION POINT`. `Deduplicator._semantic_similarity_check` is stubbed. Exact content hash, canonical URL, and title/org token matching are active.
   * *Phase 3 Action*: Introduce lightweight local embedding models (e.g., SentenceTransformers) for fuzzy cross-source similarity.
4. **Distributed Task Queue**:
   * *Current State*: Ingestion is triggered via API (`POST /api/v1/ingestion/trigger-mock`) or direct async calls.
   * *Phase 4 Action*: Introduce Redis + Celery / ARQ worker daemon for scheduled background polling.

---

## 5. Verification Status

* **Alembic Clean Database Migration**: **VERIFIED** (`ae04da361e40` -> `ad8ee8a54748`)
* **SQLite Table Inspection**: **VERIFIED** (All 9 tables confirmed in `sqlite_master`)
* **Foundation Tests (`tests/test_foundation.py`)**: **7/7 PASSED**
* **API Endpoint Tests (`tests/test_api_endpoints.py`)**: **5/5 PASSED**
* **Hardening Tests (`tests/test_audit_hardening.py`)**: **8/8 PASSED** (Idempotency, Normalization, Timeouts, FastFilter edge cases, URL canonicalization, and Inactive connectors)
