# SIGNAL 📡 — AI Gateway & Intelligence Architecture

SIGNAL employs an **AI Gateway Pattern** designed for provider neutrality, task-based specialization, strict cost control, and deterministic failover.

---

## 1. Architectural Principles

1. **Vendor Agnostic**: Business logic never imports or depends directly on vendor SDKs (`google.generativeai`, `openai`, etc.). All calls pass through the `BaseAIProvider` abstraction.
2. **Deterministic Pre-Filtering**: Over 90% of raw internet chatter is filtered out using regex patterns, keyword gates, and content hash comparisons before touching an LLM.
3. **Task-Specialized Routing**: Different tasks have different latency, context, and cost requirements. SIGNAL routes each discrete task to the most appropriate model.
4. **Resilient Cascading Failover**: If an upstream model is rate-limited, unavailable, or raises an error, the `AIRouter` automatically cascades to secondary and fallback providers without throwing 500 errors to end users.

---

## 2. Gateway Architecture

```text
               ┌───────────────────────────────┐
               │    SIGNAL Ingestion Pipeline  │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │           AIRouter            │
               │   • Task Routing Policy       │
               │   • Fallback Management       │
               │   • Health & Availability     │
               └───────────────┬───────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   NVIDIA NIM    │   │  Google Gemini  │   │     OpenAI      │
│  (Meta LLaMA)   │   │  (Flash / Pro)  │   │  (GPT-4o mini)  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │ (Terminal Fallback)
                               ▼
                      ┌─────────────────┐
                      │  MockAIProvider │
                      │ (Deterministic) │
                      └─────────────────┘
```

---

## 3. Core AI Tasks

### 3.1 Classification (`classify`)
* **Objective**: Determine whether an announcement represents a valid student/developer opportunity and infer its initial category.
* **Input**: Raw text snippet (title + summary).
* **Output**:
  ```json
  {
    "is_opportunity": true,
    "category": "competitive_programming",
    "confidence": 0.95,
    "reasoning": "Detected explicit programming contest format with cash rewards and student eligibility."
  }
  ```
* **Routing Strategy**: Fast, high-throughput model (e.g., Gemini 1.5 Flash, LLaMA-3.1-8B, or deterministic Mock).

### 3.2 Structured Extraction (`extract`)
* **Objective**: Extract standardized opportunity fields with dates, deadlines, eligibility criteria, and organizer info.
* **Input**: Full announcement text.
* **Output**:
  ```json
  {
    "title": "TCS CodeVita Season 12",
    "organization": "TCS",
    "category": "competitive_programming",
    "event_type": "competition",
    "status": "registration_open",
    "eligibility": "B.Tech/M.Tech graduating batch 2025-2027",
    "target_audience": "Engineering students & coders",
    "application_url": "https://campus.tcs.com/codevita",
    "events": [
      {
        "event_type": "registration_closing",
        "title": "Registration Deadline",
        "deadline_date": "2026-10-15T23:59:59Z",
        "is_critical": true
      }
    ],
    "summary": "...",
    "confidence": 0.94
  }
  ```
* **Routing Strategy**: High-precision JSON extraction model (NVIDIA LLaMA-3.1-70B, Gemini 1.5 Pro, or GPT-4o-mini).

### 3.3 Summarization (`summarize`)
* **Objective**: Generate concise 3-bullet actionable digests for push notifications and mobile feeds.
* **Output**: Executive summary + Key highlights + Action items.

### 3.4 Ambiguity Verification (`verify`)
* **Objective**: Ingest two ambiguous opportunity/discovery records where deterministic confidence is marginal ($0.70 \le \text{confidence} < 0.90$) and decide whether they describe the identical real-world event.
* **Input**: JSON payload comparing Organization, Titles, Dates, Deadlines, Categories, and Content Snippets.
* **Output (Structured Pydantic `AIVerificationDecision`)**:
  ```json
  {
    "is_same_opportunity": true,
    "confidence": 0.88,
    "rationale": "Both describe TCS CodeVita Season 13 despite minor title wording variation across campus portal and aggregator.",
    "field_reconciliations": {
      "deadline": "Official portal registration deadline (2026-10-15) selected over secondary aggregator.",
      "application_url": "Direct portal URL chosen."
    }
  }
  ```
* **Budget Policy & Rate Limiting (`AIUsagePolicy`)**:
  * Run-level call counter with hard limit (`MAX_AI_VERIFICATION_CALLS_PER_RUN = 20`).
  * If the budget is exhausted, further ambiguous merges are safely diverted to the human review queue (`VerificationReview`) rather than throwing runtime errors or incurring unbudgeted API costs.


---

## 4. Configuration & Provider Setup

Providers are configured strictly via environment variables without hardcoded credentials:

```env
AI_PRIMARY_PROVIDER=mock
AI_SECONDARY_PROVIDER=gemini
AI_FALLBACK_PROVIDER=openai

AI_ROUTING_CLASSIFICATION=mock
AI_ROUTING_EXTRACTION=mock
AI_ROUTING_SUMMARIZATION=mock

NVIDIA_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
```

When running in offline or test mode, setting `AI_PRIMARY_PROVIDER=mock` executes the entire pipeline with 100% deterministic results, zero API cost, and zero external network calls.
