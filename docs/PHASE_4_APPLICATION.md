# SIGNAL 📡 — Phase 4: Production Application Platform & Web Terminal

## 1. Overview & Vision

SIGNAL Phase 4 transforms the platform into an end-to-end **Production Application Platform**. While Phases 0 through 3 established the intelligence infrastructure — live web connectors, multi-tier deduplication, entity resolution, lifecycle state tracking, relevance scoring, and cross-source fact consensus — Phase 4 provides students and developers with a high-density, technical **"Intelligence Terminal"**.

The application replaces generic social/job-board patterns with a purpose-built decision support interface designed specifically for competitive programmers, hackathon competitors, and student developers tracking high-value announcements like TCS CodeVita, Smart India Hackathon, Google Summer of Code, and major fellowships.

---

## 2. Architecture & Tech Stack

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        SIGNAL Web Terminal                             │
│       React 18 + TypeScript + Vite + Tailwind CSS + Lucide Icons       │
├──────────────────────────────────┬─────────────────────────────────────┤
│  Dashboard & Radar               │  Opportunity Feed & Search          │
│  - Top Priority Intelligence Hero│  - Category Pills (Hackathons, ...) │
│  - For You (Personalized Feed)   │  - Multi-Criteria Filtering         │
│  - Imminent Deadlines (<3d, <7d) │  - Verification Tiers & Reliability │
├──────────────────────────────────┼─────────────────────────────────────┤
│  Deep Opportunity View           │  Saved & Followed Opportunities     │
│  - Stepped Lifecycle Timeline    │  - Bookmarks ("Remember this")      │
│  - Multi-Source Fact Consensus   │  - Active Trackers ("Follow alerts")│
│  - Transparent Conflict Alerts   │                                     │
│  - Corroborating Source Provenance│  Profile & Preferences Matrix       │
│  - "Your Match" Personalization  │  - Weighted Interest Sliders        │
│                                  │  - Relevance Threshold Dial         │
├──────────────────────────────────┴─────────────────────────────────────┤
│  Human Review & Ambiguity Queue  │  System Telemetry & Source Registry │
│  - Duplicate Candidate Adjudication - Real-Time Source Health Scores   │
│  - Field Conflict Resolution     │  - Raw Discovery Stream & Audit     │
└──────────────────────────────────┴─────────────────────────────────────┘
                                   │ HTTP/JSON (REST)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        SIGNAL FastAPI Backend                          │
│                                                                        │
│  GET /api/v1/dashboard/overview   → Single-roundtrip dashboard aggregate│
│  GET /api/v1/users/active         → Auto-bootstrapped student profile  │
│  POST/DEL /users/.../save         → Optimistic bookmarking             │
│  POST/DEL /users/.../follow       → Deadline subscription tracking     │
│  GET /api/v1/relevance/evaluate   → Personalization & eligibility score│
│  GET /api/v1/verification/queue   → Ambiguous candidate resolution     │
│  GET /api/v1/sources              → Monitored publisher health metrics │
│  GET /app                         → SPA static production mount        │
└────────────────────────────────────────────────────────────────────────┘
```

### Stack Components
- **Frontend Core**: React 18, TypeScript (strict mode), React Router v6.
- **Build System**: Vite 5 with Rollup chunking and automated SSD build caching.
- **Styling**: Tailwind CSS with custom terminal slate/emerald/amber theme and tabular font metrics.
- **Backend**: FastAPI with async SQLAlchemy, Alembic migrations, and CORS integration.
- **Database**: SQLite (dev) / PostgreSQL (production) with complete schema parity.

---

## 3. Key Features & Terminal Views

### 3.1 Intelligence Radar (Dashboard)
- **Aggregated Metric Counters**: Instant visibility into total tracked opportunities, active lifecycle phases, verified sources, and approaching deadlines.
- **Top Priority Hero Card**: Highlights the highest-priority urgent program (e.g. TCS CodeVita or Smart India Hackathon closing in $<3$ days) with contextual rationale and direct portal access.
- **For You Personalized Feed**: Surfaces opportunities dynamically ranked according to the active student's skill profile, academic graduation year, and domain interests.
- **Imminent Deadlines Watch**: Color-coded urgency alerts ($\le 3$ days rose, $\le 7$ days amber) for active registration deadlines.

### 3.2 Opportunity Intelligence Feed
- **Multi-Criteria Search**: Real-time filtering across titles, canonical names, summaries, technologies, and tags.
- **Category Filter Tabs**: Quick pivoting across `Hackathons`, `Contests`, `Internships`, `Student Programs`, `Fellowships`, `Scholarships`, and `AI Competitions`.
- **Verification Level Toggles**: Filter between `All`, `Official Only`, and `Verified Only`.
- **Dual-Action State**: Instant Bookmark (save for later) vs Track (follow for deadline notifications).

### 3.3 Deep Intelligence Breakdown (Opportunity Detail)
- **Intelligence Overview**: Transparent trust gauge displaying confidence score ($0-100\%$) and official publisher presence.
- **Your Personal Match Dial**: Detailed score breakdown across Skill Alignment, Domain Relevance, Interest Resonance, and Academic Eligibility, with matched skill chips and graduation mismatch warnings.
- **Lifecycle Milestone Timeline**: Interactive stepped timeline showing past, active, and upcoming phases (e.g. Registration $\rightarrow$ Round 1 Coding Test $\rightarrow$ Results).
- **Multi-Source Fact Consensus**: Displays field-level consensus from Phase 3 (e.g. `registration_deadline`, `prize_pool`) with source agreement ratios ($X/Y$ sources, percentage).
- **Source Conflict Warnings**: Flags discrepancies across aggregators and highlights official resolved values.
- **Source Provenance Evidence**: Lists all corroborating sources with URLs, reliability scores, and observation timestamps.

### 3.4 Saved & Followed Hub
- **Bookmarked Opportunities**: Stores curated listings for quick reference.
- **Followed Program Watches**: Tracks opportunities actively subscribed to deadline reminders and state changes.
- **Optimistic UI**: Instant bookmark/follow toggles with background API synchronization and automatic rollback on failure.

### 3.5 Student Profile & Preference Matrix
- **Academic Profile**: Graduation year, degree, university, GitHub profile, and primary domain.
- **Skills Inventory**: Add and remove technical skills (e.g. Python, PyTorch, React, Algorithms).
- **Weighted Interest Matrix**: $0.0 - 1.0$ continuous sliders for fine-tuning recommendation scores.
- **Relevance Threshold**: Threshold control ensuring low-scoring noise is suppressed.
- **Telegram Alert Integration**: Configuration for real-time priority notification dispatch.

### 3.6 Human Review Queue & Telemetry
- **Ambiguity Adjudication**: Approve, reject, or merge candidate duplicate opportunities flagged during entity resolution.
- **Data Conflict Resolution**: Choose between competing aggregator values with manual official overrides.
- **System Telemetry**: Real-time health, base URLs, and reliability ratings for all registered sources.

---

## 4. Running the Application

### Option A: Unified FastAPI Mount (Production Mode)
FastAPI serves the pre-built React application directly:
```bash
# Build web terminal (generates apps/web/dist)
powershell -ExecutionPolicy Bypass -File apps/web/build.ps1

# Run FastAPI backend
python -m uvicorn apps.api.main:app --port 8000 --reload
```
Navigate to: **`http://localhost:8000/app`** (API docs at `http://localhost:8000/docs`).

### Option B: Vite Development Server (HMR Mode)
```bash
# Terminal 1: Start Backend API
python -m uvicorn apps.api.main:app --port 8000 --reload

# Terminal 2: Start Vite Dev Server
powershell -ExecutionPolicy Bypass -File apps/web/dev.ps1
```
Navigate to: **`http://localhost:5173`** (API requests are proxied automatically to `localhost:8000`).

---

## 5. Verification & Testing

- **Backend Integration Tests**: `tests/test_saved_and_dashboard.py` (Save/Follow lifecycle, active user bootstrap, dashboard aggregation).
- **API Endpoint Tests**: `tests/test_api_endpoints.py` (Full CRUD, enum resilience, event queries).
- **Frontend Compilation**: `tsc && vite build` completed with zero TypeScript errors across 1,604 modules.
- **Overall Suite**: All 123 tests passing with 0 regressions.
