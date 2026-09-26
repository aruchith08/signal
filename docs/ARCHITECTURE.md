# SIGNAL 📡 — System Architecture

> **Your Personal Opportunity Intelligence Network**
> *Discover → Understand → Verify → Personalize → Alert*

---

## 1. Architectural Philosophy

SIGNAL is **NOT** a simple chatbot and **NOT** an LLM that randomly queries the internet.

SIGNAL is an **Event + Opportunity Intelligence Platform**. The core tenet of the platform is:

> **Use deterministic software systems wherever possible; use AI strictly where semantic extraction and language comprehension add genuine value.**

Every piece of internet content does NOT get piped to an LLM. Instead, SIGNAL employs a staged pipeline:

```text
RAW ANNOUNCEMENT
       ↓
CHANGE DETECTION (Content Hash)
       ↓
FAST FILTERING (Deterministic Regex / Keyword Rules)
       ↓
AI CLASSIFICATION (Fast / Cost-Effective Provider)
       ↓
AI EXTRACTION (High-Precision Provider)
       ↓
SOURCE VERIFICATION & CONFIDENCE SCORING
       ↓
DEDUPLICATION (Canonical Matching)
       ↓
CANONICAL OPPORTUNITY STORE (PostgreSQL)
       ↓
PERSONALIZATION & RELEVANCE SCORING
       ↓
PRIORITY ARBITRATION
       ↓
MULTI-CHANNEL NOTIFICATIONS (Telegram, etc.)
```

---

## 2. End-to-End System Layers

```text
                          ┌────────────────────────┐
                          │ External Sources       │
                          │ Portals, APIs, Feeds   │
                          └───────────┬────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. INGESTION & SOURCE INTELLIGENCE LAYER                               │
│    • Central Source Catalog & Registry (metadata, polling policies)    │
│    • ResilientHTTPClient (connection pooling, backoff, GET/POST/GraphQL│
│    • Modular Live Connectors (CodeChef, HackerRank, LeetCode, GSoC,    │
│      MyGov, MLH, Codeforces, GitHub Blog, SIH)                         │
│    • Source Snapshot Persistence (SHA-256 snapshot hashing)            │
│    • Meaningful Change Detection (strips volatile counters/cookies)    │
│    • Deadline Intelligence (DateExtractor & DeadlineEvaluator)         │
│    • Source Health Telemetry (HEALTHY, DEGRADED, FAILING, DISABLED)    │
│    • FastFilter: High-throughput regex/keyword rule gates              │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │ Filtered Candidates
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. INTELLIGENCE LAYER (AI GATEWAY)                                     │
│    • AIRouter: Task-based routing & automatic fallback                 │
│    • Providers: NVIDIA NIM, Google Gemini, OpenAI, MockProvider        │
│    • Tasks: Classify ➔ Extract Structured Schema ➔ Summarize          │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │ Normalized Opportunity DTO
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. OPPORTUNITY INTELLIGENCE, WATCH & LIFECYCLE LAYER                   │
│    • Domain Classifier: Actionable vs. Informational classification    │
│    • Program Watch Engine: Active program monitoring & evidence match  │
│    • Organization Alias Resolution (OrganizationAlias canonicalization)│
│    • 5-Tier Deterministic Entity Resolver (with false-merge guards)     │
│    • Lifecycle Engine: Idempotent event logging & state machine        │
│    • Multi-Tiered Trust Hierarchy (Government/Company > Platforms)    │
│    • Deduplication by URL canonicalization, title & organization       │
│    • Confidence calculation (0-100 score)                              │
│    • Details: docs/DOMAIN_MODEL.md, docs/PROGRAM_WATCH_ENGINE.md       │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │ Verified Opportunity
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. PERSISTENCE & API LAYER                                             │
│    • PostgreSQL / Async SQLAlchemy 2.0 (with SQLite support)           │
│    • Normalized Entities: Organizations, Aliases, Sources, Snapshots,  │
│      RawDiscoveries, Opportunities, Events, ProgramWatches, Matches    │
│    • FastAPI REST Endpoints (/api/v1/...) with Pydantic v2 validation  │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │ Opportunity & Events
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. PERSONALIZATION, RELEVANCE INTELLIGENCE & NOTIFICATION SUBSYSTEM    │
│    • User Intelligence: UserProfile, UserInterest, Skills, Preferences │
│    • Conservative Academic Eligibility Evaluator (Degree, Year, Grad)  │
│    • Deterministic Relevance Scorer (0-100 formula + ineligibility cap)│
│    • Transparent Explainability Engine (Human-readable factor breakdown│
│    • 10-Step Notification Decision Engine (Rules, Caps, Bypass Protocol│
│    • Anti-Fatigue Subsystem: Exact dedup, 12h cooldown, daily limits   │
│    • Timezone-Aware Quiet Hours Throttler (Safe cross-midnight logic)  │
│    • Priority Escalator: Deadline urgency (<6h, <24h, <3d, <7d)        │
│    • Multi-Channel Dispatcher: BaseNotifier, MockNotifier, Telegram    │
│    • Interactive Telegram Bot Handler: /start, /status, /preferences   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Component Breakdown

### 3.1 Connector & Source Registry Subsystem (`connectors/`, `services/sources/`)
* **`SourceRegistry` & `SourceDefinition`**: Central catalog mapping source slugs to metadata, categories, connector classes, priority levels, and polling policies (`REALTIME`, `FREQUENT`, `STANDARD`, `DAILY`, `MANUAL`).
* **`BaseConnector`**: Standardized lifecycle interface (`health_check`, `fetch_raw_items`).
* **Active Production Connectors**:
  * `competitive_programming/`: Codeforces (REST), CodeChef (REST API), HackerRank (REST API), LeetCode (GraphQL POST).
  * `open_source/`: GSoC / Google Open Source Blog (Atom/JSON feed).
  * `hackathons/`: MLH (HTML scraper), Smart India Hackathon (HTML/Modals).
  * `government/`: MyGov Innovate (HTML scraper).
  * `industry_blogs/`: GitHub Blog (RSS 2.0 XML).
* **Documented Limitations**: Devfolio (Cloudflare TLS fingerprinting) and MeitY (client-side dynamic SPA) are cataloged as inactive with documented headless/reverse-engineering roadmaps.

### 3.2 Ingestion Engine & Change Intelligence (`services/ingestion/`, `services/intelligence/`)
* **Snapshot Persistence**: Saves raw text payloads to `SourceSnapshot` with computed SHA-256 hash.
* **`MeaningfulChangeDetector`**: Normalizes whitespace, strips volatile timestamps, session tokens, and view counters. Computes semantic hashes and identifies structural changes (status changes, deadline shifts, title modifications).
* **Deadline Intelligence (`DateExtractor` & `DeadlineEvaluator`)**: Regex extraction across 6 date formats; evaluates deadline changes to emit `DEADLINE_ANNOUNCED`, `DEADLINE_EXTENDED`, or `DEADLINE_SHORTENED`.
* **Health Telemetry**: Tracks response times, error rates, and consecutive failures. Transitions source health across `HEALTHY` -> `DEGRADED` -> `FAILING` -> `DISABLED`.
* **`FastFilter`**: Evaluates title and body against curated positive signals (e.g. `hackathon`, `registration`, `deadline`, `eligibility`, `contest`, `internship`) and negative disqualifiers (sports, movies, clickbait). Guarantees zero unnecessary AI spend.

### 3.3 AI Gateway & Router (`services/intelligence/`)
* **Decoupled Architecture**: No business logic imports a specific vendor SDK.
* **`AIRouter`**: Routes each discrete task to the optimal provider:
  * **Classification**: Fast/low-cost model.
  * **Extraction**: Precision structured-output model.
  * **Summarization**: Concise synthesis model.
* **Failover Protocol**: When a primary provider exhausts rate limits or errors, requests automatically cascade to secondary and fallback providers.

### 3.4 Verification & Entity Resolution Subsystem (`services/lifecycle/`)
* **Organization Alias Resolution**: Resolves acronyms, abbreviations, and common naming variations (e.g., "Google Summer of Code" -> "Google", "Ministry of Electronics and Information Technology" -> "MeitY") against `OrganizationAlias` records before creating duplicate organizations.
* **5-Tier Entity Resolver**:
  1. Exact canonical URL match.
  2. Organization ID + normalized title match.
  3. Strict domain + year match.
  4. Token similarity match (with false-merge safety guards).
  5. Fallback creation of new canonical record.
* **Trust Hierarchy**:
  1. **Highest Trust**: Official Government Portals (AICTE, MeitY, MyGov), Official Company Portals (TCS, Google, Microsoft).
  2. **High Trust**: Official Universities (IITs, IISc, NITs), Verified Platforms (Devfolio, Kaggle).
  3. **Medium-High Trust**: Curated Competition Platforms (Unstop, HackerEarth).
  4. **Medium Trust**: Reputable Technology Journalism & Press Releases.
  5. **Lower / Low Trust**: Social media posts, third-party blogs.

### 3.5 Personalization & Notification Subsystem (`services/personalization/`, `services/notifications/`)
* **User Intelligence & Profiles**: Extends `User` with `UserProfile` (degree, grad year, current academic year, timezone), weighted interests (`UserInterest`, 0.0 to 1.0), normalized skills (`Skill`, `UserSkill`), and notification preferences (`UserNotificationPreference`).
* **Deterministic Relevance Scoring**:
  * 0–100 composite score based on: Direct Interest Match (30 pts), Category Alignment (15 pts), Required Skill Match (15 pts), Academic Eligibility (15 pts), Program Watch Match (15 pts), and Opportunity Priority (10 pts).
  * Strict ineligibility cap: If the user is identified as `INELIGIBLE`, the score is hard-capped at 25/100 to prevent false-positive alert dispatch.
* **Conservative Eligibility Evaluator (`EligibilityEvaluator`)**: Regex matching against degrees (B.Tech, B.E., M.Tech, MCA, BCA, MS, Ph.D, B.Sc) and graduation/academic year validation. Uses a conservative ternary model (`ELIGIBLE`, `INELIGIBLE`, `UNKNOWN`), where missing data evaluates to `UNKNOWN` rather than rejecting opportunities.
* **Explainability Generator (`ExplanationGenerator`)**: Generates transparent, human-readable breakdown factors for why an opportunity scored as it did.
* **10-Step Notification Decision Engine (`NotificationDecisionEngine`)**:
  1. Delivery mode check (`MUTED`, `DAILY_DIGEST`, `REALTIME`).
  2. Eligibility gating (drops `INELIGIBLE`).
  3. Relevance threshold validation (defaults to min score 60).
  4. Exact `(user, opportunity, event)` deduplication.
  5. 12-hour opportunity cooldown suppression.
  6. Urgency assessment & priority escalation.
  7. Timezone-aware quiet hours throttling (with cross-midnight safety).
  8. Daily notification rate limit enforcement (default: max 5 alerts/day).
  9. Critical bypass evaluation (<24h deadlines bypass quiet hours and rate limits).
  10. Dispatch routing & complete audit record logging.
* **Anti-Fatigue System**: Combines exact event deduplication, 12h cooldown, configurable daily limits, and quiet hours.
* **Telegram Subsystem (`TelegramNotifier`, `TelegramBotHandler`)**:
  * Markdown-safe message formatting with registration links and urgency headers.
  * Bot handler supporting `/start [token]` for 1-click account linking, `/status`, `/preferences`, `/subscribe`, `/unsubscribe`, and `/help`.
  * Multi-provider abstraction (`BaseNotifier`, `MockNotifier`, `TelegramNotifier`) enabling offline zero-credential testing.

### 3.6 Cross-Source Verification, Consensus & AI Intelligence (Phase 3)
* **`SourceTrustService`**: Computes deterministic trust scores ($0.20$ to $1.00$) based on domain suffix heuristics (`.gov.in`, `.nic.in`, `.ac.in`, `.edu`), known curated platform registries, and official host matching.
* **`MergeGuardrails`**: Enforces hard negative constraints before any entity merge can occur. Explicitly rejects merges with organization mismatches, conflicting academic/calendar years, differing seasonal tags (e.g. Summer vs. Winter), or disjoint categories.
* **`CrossSourceResolver`**: 4-level staged entity resolution pipeline:
  1. *Level 1 (Exact URL / External ID)*: Confidence $1.00$ — instant link.
  2. *Level 2 (Strong Deterministic)*: Confidence $0.90$–$0.99$ — matching canonical name, year, and stop-word filtered title tokens.
  3. *Level 3 (Heuristic Match)*: Confidence $0.75$–$0.89$ — fuzzy title similarity and host matching.
  4. *Level 4 (Semantic Vector Similarity)*: Cosine similarity of embedding vectors ($0.60$–$0.89$). If confidence is ambiguous ($0.70 \le \text{confidence} < 0.90$), automatically routes to AI Verification or Human Review. Auto-merges only if $\ge 0.95$ and guardrails pass.
* **`SemanticMatcher`**: Computes cosine similarities using pluggable `EmbeddingProvider` (`MockEmbeddingProvider` active offline, OpenAI/NVIDIA in production) across canonical invariant text representations.
* **`AIVerificationService`**: Provides structured JSON decision reasoning for ambiguous merges ($0.70 \le \text{confidence} < 0.90$) governed by `AIUsagePolicy` with rate limiting (`MAX_AI_VERIFICATION_CALLS_PER_RUN = 20`) to avoid runaway costs.
* **`ConflictDetector` & `VerificationEngine`**: Detects fact-level discrepancies across independent sources (deadlines, URLs, eligibility, year, season). Applies source trust dominance (official sources win) to establish canonical consensus while recording open conflicts.
* **`ReviewQueueService` (`VerificationReview`)**: Human review queue allowing manual approval, rejection, and priority triage (`critical`, `high`, `medium`, `low`) for unresolved conflicts and ambiguous merges.

---

## 10. Phase 5A: Automated Scheduler & Structured Change Intelligence

* **`AsyncIOScheduler` & Coordinator**: Singleton scheduler managed via FastAPI lifespan hooks. Runs periodic coordinator jobs every 5 minutes, evaluating `is_active`, `scheduler_enabled`, `monitor_frequency_minutes`, and `polling_policy` (`high_priority`, `medium_priority`, `low_priority`, `archival`, `adaptive`).
* **`ScheduledJob` Audit Subsystem**: Captures every ingestion run with duration, items processed, error messages, and success/failure status.
* **`OpportunityChangeDetector`**: Compares existing canonical opportunities against incoming updates **prior to field modification**, generating `ChangeSet` records with semantic `ChangeType` and `PriorityLevel` while enforcing strict duplicate prevention.
* **Scheduler Observability API**: REST endpoints at `/api/v1/scheduler` providing operational status, paginated job history, and on-demand trigger endpoints (`/poll/{source_slug}`, `/poll-all`).



