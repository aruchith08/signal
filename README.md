# SIGNAL 📡

> **Your Personal Opportunity Intelligence Network**  
> *Never miss important opportunities, announcements, competitions, hackathons, internships, student programs, government initiatives, scholarships, fellowships, and tech events.*

---

## What is SIGNAL?

The internet announces high-value opportunities across hundreds of disconnected websites—from competitive programming platforms and hackathon portals to government ministries and Fortune 500 campus programs.

**SIGNAL** is an intelligent monitoring and extraction platform that turns the internet's firehose into a verified, personalized stream of opportunities for students and developers:

```text
THE INTERNET ANNOUNCES
        ↓
 SIGNAL DISCOVERS
        ↓
 SIGNAL UNDERSTANDS
        ↓
  SIGNAL VERIFIES
        ↓
SIGNAL DECIDES RELEVANCE
        ↓
 THE USER GETS ALERTED
```

SIGNAL is **not** a chatbot and does not blindly prompt an LLM on every webpage. It is a production-engineered **Event + Opportunity Intelligence Platform** combining high-speed deterministic rules, change detection, AI gateway abstraction, multi-source verification, and targeted alerts.

---

## Core Opportunity Categories

* **Competitive Programming**: CodeChef, Codeforces, LeetCode, HackerRank, AtCoder
* **Hackathons**: Devfolio, Unstop, Devpost, MLH, Smart India Hackathon
* **Major Company Programs**: TCS CodeVita, Infosys HackWithInfy, Flipkart GRiD, Microsoft Imagine Cup, Google Student Programs
* **AI & Machine Learning**: Kaggle, Hugging Face, DrivenData
* **Government Initiatives**: AICTE, MeitY, IndiaAI, MyGov, DST, ISRO, DRDO
* **Internships & Research**: SDE Internships, IIT/IISc Research Internships, Summer Programs
* **Scholarships & Fellowships**: National & Corporate student grants

---

## Architecture Highlights

1. **Deterministic Fast-Filtering**: Over 90% of raw content is filtered out using regex rules and SHA-256 change detection before ever contacting an AI model.
2. **AI Gateway & Router**: Clean provider abstraction (`BaseAIProvider`, `AIRouter`) supporting NVIDIA NIM, Google Gemini, OpenAI, and a deterministic `MockAIProvider`. Automatic fallback ensures zero downtime.
3. **Decoupled Opportunity & Event Model**: Opportunities have discrete lifecycle events (`REGISTRATION_OPEN`, `DEADLINE_CHANGED`, `RESULTS_RELEASED`) enabling precise deadline alerts.
4. **Source Verification Hierarchy**: Strict trust levels (Government/Company > Platforms > News > Social Media) prevent unverified spam alerts.
5. **Multi-Channel Alert Abstraction**: Priority-driven dispatcher (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) with initial support for Telegram.

---

## Monorepo Layout

```text
signal/
├── apps/
│   ├── api/                    # FastAPI backend service
│   │   ├── config.py           # Pydantic Settings
│   │   ├── database.py         # SQLAlchemy 2.0 Async engine & sessions
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── models/             # Normalized ORM models
│   │   ├── schemas/            # Pydantic v2 validation schemas
│   │   └── routers/            # REST API endpoints
│   └── web/                    # React + Vite + Tailwind Intelligence Terminal
├── connectors/                 # Monitored source connectors
│   ├── base_connector.py       # Abstract connector contract
│   ├── mock_connector.py       # Sample opportunities generator
│   └── [categories]/           # Category-specific connectors
├── services/
│   ├── ingestion/              # Change detection, FastFilter, pipeline
│   ├── intelligence/           # AI Gateway, router, and provider adapters
│   ├── personalization/        # Student relevance scoring, eligibility evaluator
│   ├── verification/           # Multi-source trust, cross-source resolution, consensus
│   └── notifications/          # Priority dispatcher & Telegram bot
├── shared/                     # Enums, constants, slug and hash utilities
├── docs/                       # Architectural and database specifications
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── AI_ARCHITECTURE.md
│   ├── PHASE_4_APPLICATION.md
│   └── ROADMAP.md
├── docker/
│   ├── docker-compose.yml      # PostgreSQL + Redis + API
│   └── Dockerfile.api
├── pyproject.toml              # Project dependencies & build metadata
└── README.md
```

---

## Quickstart Guide

### Prerequisites
* Python 3.11+
* Node.js v18+ & npm
* (Optional) Docker & Docker Compose for PostgreSQL

### 1. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run FastAPI backend
python -m uvicorn apps.api.main:app --port 8000 --reload
```
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **System Health**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 2. Launch Web Intelligence Terminal (Phase 4)

#### Option A: Unified FastAPI Web Mount (Production Mode)
```bash
# Build the production bundle into apps/web/dist
powershell -ExecutionPolicy Bypass -File apps/web/build.ps1

# The web terminal is automatically mounted by FastAPI at:
# http://localhost:8000/app
```

#### Option B: Vite Development Server with Hot Reload
```bash
powershell -ExecutionPolicy Bypass -File apps/web/dev.ps1
# Open http://localhost:5173 (proxies /api requests to localhost:8000)
```

---

## Documentation

* [System Architecture](docs/ARCHITECTURE.md)
* [Database Schema & Models](docs/DATABASE.md)
* [AI Gateway & Router](docs/AI_ARCHITECTURE.md)
* [Phase 4: Web Application Platform](docs/PHASE_4_APPLICATION.md)
* [Development Roadmap](docs/ROADMAP.md)

---

## License
MIT License
