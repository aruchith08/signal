# SIGNAL 📡 — Development Roadmap

SIGNAL is built in focused, iterative phases to guarantee architectural cleanliness, testability, and operational stability.

---

## 📍 Phase 0: Foundation (Completed)
* [x] Monorepo structure & production configuration
* [x] Normalized domain models (Organizations, Sources, Opportunities, Events, Users, Notifications)
* [x] SQLAlchemy 2.0 Async database layer + Alembic migrations setup
* [x] AI Gateway abstraction (`BaseAIProvider`, `AIRouter`, `MockAIProvider`, Provider stubs)
* [x] Source Connector abstraction (`BaseConnector`, `MockConnector`)
* [x] Deterministic pre-filter (`FastFilter`) for cost & noise reduction
* [x] RESTful API endpoints for health, opportunities, organizations, sources, and events
* [x] Ingestion pipeline coordinator (`IngestionPipeline`)
* [x] Architectural documentation suite

---

## 📍 Phase 0.5: Foundation Audit & Hardening (Completed)
* [x] Eliminated mock AI data leaks in production/testing
* [x] Replaced fake title slug deduplication with multi-tier content hash and canonical URL matching
* [x] Hardened URL canonicalization stripping tracking params (`utm_*`, `fbclid`, `ref`)
* [x] Fixed FastFilter false negatives with case-insensitive tokenization and scoring
* [x] Implemented resilient timeout guards and failover in `AIRouter`
* [x] Dual pagination support and 20 passing unit tests

---

## 📍 Phase 1A: Live Source Intelligence (Completed)
* [x] Selected and verified 3 diverse live internet sources (API, RSS, HTML Portal)
* [x] Built shared `ResilientHTTPClient` with connection pooling, timeouts, and exponential backoff retry
* [x] Created live `CodeforcesConnector` querying official Codeforces REST API
* [x] Created live `GitHubBlogConnector` parsing official GitHub Blog RSS 2.0 XML
* [x] Created live `SIHConnector` parsing official Smart India Hackathon problem statements & modals
* [x] Implemented `RawDiscovery` data model and Alembic migration `007ae98cf30c`
* [x] Upgraded `IngestionPipeline` with end-to-end audit logging, change detection, and status transitions
* [x] Built Discoveries REST API (`GET /api/v1/discoveries`, `GET /api/v1/discoveries/{id}`)
* [x] Added live trigger endpoint (`POST /api/v1/ingestion/trigger-live/{source_slug}`)
* [x] Comprehensive mock-safe test suite with 27 passing tests
* [x] Live execution verified with 52 raw discoveries, 37 canonical opportunities ingested

---

## 📍 Phase 1B: Opportunity Intelligence & Lifecycle Engine (Completed)
* [x] Formal distinction between Raw Discoveries, Canonical Opportunities, and Opportunity Events
* [x] Non-actionable & informational content isolation (audited in RawDiscovery, 0 spurious opportunities)
* [x] Multi-stage opportunity lifecycle state machine (`announced` -> `registration_open` -> `deadline_extended` -> `results_announced`)
* [x] 5-Tier conservative deterministic entity resolution with strict false-merge guardrails
* [x] Opportunity alias tracking (`OpportunityAlias`) for nicknames, acronyms, and historical variants
* [x] Event idempotency guarantees on repeated polling intervals
* [x] Alembic migration `467ad4d0d1de` with SQLite batch-alter support
* [x] Updated REST APIs: `GET /api/v1/opportunities/{id}/events`, `current_state`, `year`, and `classification` filters
* [x] 40 passing unit tests (13 dedicated domain lifecycle tests + 27 foundation tests)
* [x] Live database audit verified across 52 discoveries, 73 events, and 37 opportunities

---

## 📍 Phase 1C-A: Program Watch Engine & Watch Registry (Completed)
* [x] Program watch models (`ProgramWatch`, `ProgramWatchAlias`, `ProgramWatchKeyword`, `ProgramWatchSource`, `ProgramWatchMatch`)
* [x] Alembic migration `87f0cc14b731` with SQLite batch mode and idempotent unique constraints
* [x] 5-Tier deterministic rule-based matching engine (`EXACT_ALIAS`, `EXACT_NAME`, `EXACT_CANONICAL_NAME`, `KEYWORD_COMBINATION`, `SOURCE_ASSOCIATION`)
* [x] False-positive protection guardrail requiring distinctive keyword hits
* [x] Explainable match confidence scoring (`HIGH >= 0.90`, `MEDIUM >= 0.60`, `LOW < 0.60`)
* [x] Non-blocking pipeline integration within `IngestionPipeline` (observability without gating)
* [x] Seed registry with 15 flagship Indian & global student programs across Critical, High, and Medium tiers
* [x] Program watch REST API (`/api/v1/program-watches` CRUD, `/matches`, and `/matches/all`)
* [x] 50 unit and integration tests passing with 0 failures
* [x] Live database audit verified with 42 matches across 54 raw discoveries and 37 opportunities

---

## 📍 Phase 1C: Source Intelligence Expansion & Production-Grade Change Monitoring (Completed)
* [x] Centralized Source Catalog & Registry (`SourceDefinition`, `SourceRegistry`) with priority and polling policies
* [x] Live Verified Connectors:
  * Competitive Programming: Codeforces (REST), CodeChef (REST), HackerRank (REST), LeetCode (GraphQL)
  * Open Source: Google Summer of Code / Google Open Source Blog (Atom/JSON feed)
  * Hackathons: Major League Hacking (HTML), Smart India Hackathon (HTML)
  * Government: MyGov Innovate (HTML)
  * Industry Blogs: GitHub Blog (RSS)
* [x] Source Snapshot Subsystem (`SourceSnapshot` model, Alembic migration `8b4a84077d28`, payload storage & hashing)
* [x] Semantic Change Detection & Meaningful Change Filter (`MeaningfulChangeDetector` ignoring volatile timestamps/cookies/counters)
* [x] Date Extraction & Deadline Intelligence (`DateExtractor`, `DeadlineEvaluator` for `DEADLINE_ANNOUNCED`, `DEADLINE_EXTENDED`, `DEADLINE_SHORTENED`)
* [x] Organization Alias Resolution (`OrganizationAlias` model, 37 aliases seeded across 11 orgs, integrated in `EntityResolver`)
* [x] Source Health Telemetry (`HEALTHY`, `DEGRADED`, `FAILING`, `DISABLED`, response times, error tracking)
* [x] Polling CLI Runner (`scripts/poll_sources.py` with filtering by source slug, priority, and policy)
* [x] Standardized Connector Contract Test Mixin (`tests/helpers/connector_contract.py`)
* [x] REST APIs: `/api/v1/sources/{id}/health`, `/api/v1/sources/{id}/snapshots`, `/api/v1/dashboard/sources`, `/api/v1/dashboard/activity`
* [x] 63 automated tests passing (0 failures, 0 regressions)
* [x] Live database audit: 102 discoveries, 65 canonical opportunities, 104 lifecycle events, 59 program watch matches across 9 active sources

---

## 📍 Phase 2: Personalization, Relevance Intelligence & Telegram Alert System (Completed)
* [x] User Intelligence Data Models:
  * User profile attributes (degree, graduation year, current year, timezone, career interests, preferred opportunity types)
  * Weighted user interests (`UserInterest` with weight 0.0 to 1.0)
  * Normalized skill inventory & tagging (`Skill`, `UserSkill`)
  * Granular notification preferences (`UserNotificationPreference` with quiet hours, min score, delivery mode, max daily limits)
  * Alembic migration `16d32cd32477` applied with SQLite batch-alter support
* [x] Deterministic Relevance Scoring Engine (`services/personalization/`):
  * Multi-dimensional scoring formula (0–100 scale: interests, category, skills, eligibility, program watches, priority)
  * Ineligibility score cap (capped at max 25/100 to prevent false-positive notifications)
  * Transparent explainability breakdown with human-readable factor summaries
* [x] Conservative Academic Eligibility Evaluator (`EligibilityEvaluator`):
  * Regex degree matchers (B.Tech, B.E., M.Tech, MCA, BCA, MS, Ph.D, B.Sc)
  * Graduation year & current academic year bounds checking
  * Deterministic ternary status: `ELIGIBLE`, `INELIGIBLE`, `UNKNOWN`
* [x] 10-Step Notification Decision Engine (`NotificationDecisionEngine`):
  * Eligibility filter, relevance thresholding, exact (user, opp, event) deduplication
  * 12-hour opportunity cooldown, quiet hours throttling, daily rate limit checking
  * Emergency bypass protocol for critical (<24h) deadlines
* [x] Telegram Alert Subsystem (`services/notifications/`):
  * Modular `BaseNotifier`, `TelegramNotifier` (HTTP Bot API with retry & markdown escaping), `MockNotifier`
  * Interactive bot handler (`TelegramBotHandler` supporting `/start`, `/status`, `/preferences`, `/subscribe`, `/unsubscribe`, `/help`)
  * Automatic account linking via `/start <token>`
* [x] RESTful User & Notification APIs (`apps/api/routers/users.py`, `apps/api/routers/notifications.py`):
  * Profile CRUD, skills management, weighted interests, preferences update
  * Opportunity relevance preview endpoint (`GET /api/v1/users/{id}/relevance/{opportunity_id}`)
  * Telegram webhook receiver (`POST /api/v1/notifications/telegram/webhook`) and test alert trigger
* [x] Test Suite & Verification:
  * 95 automated tests passing with zero regressions across the entire platform
  * 32 new unit and integration tests dedicated to Phase 2 subsystems


---

## 📍 Phase 3: Cross-Source Verification, Advanced Deduplication & AI Intelligence (Completed)
* [x] Multi-Source Trust Engine (`services/verification/source_trust.py`):
  * Deterministic trust scoring ($0.20$ to $1.00$) based on domain suffix heuristics (`.gov.in`, `.nic.in`, `.ac.in`, `.edu`) and curated platform registries
  * Dynamic bonus attribution for verified official organization domains
* [x] Strict False-Merge Guardrails (`services/verification/merge_guardrails.py`):
  * Hard negative constraints blocking accidental merges across distinct organizations, conflicting calendar/academic years, differing seasons, or disjoint categories
* [x] 4-Level Cross-Source Entity Resolver (`services/verification/cross_source_resolution.py`):
  * Level 1 (Exact Match, $1.00$ confidence): URL / external ID match
  * Level 2 (Strong Deterministic, $0.90$–$0.99$ confidence): Canonical name, year, and stop-word filtered title token overlap
  * Level 3 (Heuristic, $0.75$–$0.89$ confidence): High string similarity and organization compatibility
  * Level 4 (Semantic Vector, $0.60$–$0.89$ confidence): Cosine similarity of embedding vectors with strict guardrails
* [x] Pluggable Semantic Vector Matcher (`services/verification/semantic_matcher.py`):
  * Invariant text synthesis, cosine similarity calculation, and pluggable `EmbeddingProvider` (`MockEmbeddingProvider` offline default)
* [x] Budget-Enforced AI Verification (`services/verification/ai_verification.py`, `services/intelligence/usage_policy.py`):
  * Structured Pydantic validation for resolving ambiguous merges ($0.70 \le \text{confidence} < 0.90$)
  * Strict run-level budget limits (`MAX_AI_VERIFICATION_CALLS_PER_RUN = 20`) with telemetry tracking
* [x] Fact-Level Consensus & Conflict Detection (`services/verification/conflict_detector.py`, `services/verification/engine.py`):
  * Fact-level verification for title, application URL, and deadlines
  * Official source dominance rule and automatic conflict recording in `verification_conflicts`
  * Updates canonical opportunity confidence, source counts, and verification status (`VERIFIED`, `LIKELY_VERIFIED`, `CONFLICTING`, `REVIEW_REQUIRED`)
* [x] Human Review Queue Subsystem (`services/verification/review_queue.py`):
  * Review queue for ambiguous matches and conflicts (`VerificationReview` model)
  * Priority triage (`critical`, `high`, `medium`, `low`) and approval/rejection resolution actions
* [x] RESTful Verification APIs (`apps/api/routers/verification.py`):
  * Opportunity verification overview (`GET /api/v1/opportunities/{id}/verification`)
  * Contributing source list (`GET /api/v1/opportunities/{id}/sources`)
  * Open conflict log (`GET /api/v1/verification/conflicts`)
  * Human review queue (`GET /api/v1/verification/review-queue`, `POST /api/v1/verification/review/{id}/approve`, `POST /api/v1/verification/review/{id}/reject`)
* [x] Comprehensive Test Suite & Schema Migrations:
  * Alembic migration `3f1c561f8361` with SQLite batch-alter support
  * 120 automated tests passing with 0 failures, 0 errors, and zero regressions across the entire platform

---

## 📍 Phase 4: Production Application Platform & Web Terminal (Completed)
* [x] Information-dense "Intelligence Terminal" for students and developers (zero generic social/clone bloat)
* [x] React 18 + TypeScript + Vite 5 + Tailwind CSS SPA architecture in `apps/web/`
* [x] Centralized HTTP API client with resilient error handling and query parsing
* [x] State Management & Optimistic UI (`AuthContext`, `ToastContext` with optimistic updates and network rollback)
* [x] Intelligence Radar Dashboard (`DashboardPage` with aggregated metrics, top priority hero card, for-you feed, upcoming deadlines)
* [x] Multi-criteria Opportunity Explorer (`FeedPage` with real-time text search, category tabs, verification level toggles)
* [x] Deep Intelligence Breakdown (`OpportunityDetailPage` with stepped lifecycle timeline, "Your Match" dial, fact consensus table, conflict warnings, source provenance)
* [x] Saved & Followed Hub (`SavedPage` distinguishing bookmarks vs active deadline tracking)
* [x] Student Profile & Preferences Matrix (`ProfilePage` with academic identity, skills inventory, weighted interest sliders, quiet hours, Telegram bot link)
* [x] Human Review & Adjudication Queue (`VerificationQueuePage` for resolving ambiguous candidate duplicates and data conflicts)
* [x] System Telemetry & Source Registry (`ActivityPage` with monitored publisher health, reliability ratings, and audit event stream)
* [x] Backend Integration & Schema Migration:
  * `UserOpportunityInteraction` data model with Alembic migration `796ad5bd0e2b`
  * `GET /api/v1/dashboard/overview` single-roundtrip aggregation endpoint
  * `GET /api/v1/users/active` demo student bootstrap endpoint (`Alex Chen`)
  * Bookmark/Follow API endpoints (`POST/DELETE /users/{id}/opportunities/{opp_id}/save` & `/follow`)
  * FastAPI static production SPA mount at `/app`
* [x] Production Build & Verification:
  * Full production Vite build (`apps/web/dist`) bundling 1,604 modules with zero errors
  * Dedicated test suite `tests/test_saved_and_dashboard.py`
  * All 123 automated platform tests passing with 0 errors and zero regressions

---

## 📍 Phase 5: Distributed Scaling & Multi-Channel Dispatch
* [ ] Distributed background worker queues (Redis + Celery or ARQ)
* [ ] Multi-channel notifications (Email digests via SendGrid / Resend, WebPush)
* [ ] Public opportunity search, calendar export (`.ics`), and RSS feeds


