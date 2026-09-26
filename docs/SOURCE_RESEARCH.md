# SIGNAL 📡 — Source Research & Ingestion Evaluation

**Date**: September 2026  
**Phase**: 1A (Live Source Intelligence)

Before building connectors, candidate sources were empirically evaluated to determine their actual data access mechanisms, authentication requirements, rate limits, and reliability.

---

## 1. Candidate Source Evaluation Matrix

| Source Name | Category | Access Method | Official API? | RSS/Atom? | Auth Required? | Rate Limits | Recommended Polling | Reliability Rating | Implementation Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Codeforces** | Competitive Programming | Official REST API | **Yes** (`/api/contest.list`) | No | No (Public) | ~1-5 req/sec | Every 30–60 min | **Highest (5/5)** | **Selected for Phase 1A (Source 1)** |
| **GitHub Tech Blog** | Technology / Student | Official RSS 2.0 | Yes (REST API also available) | **Yes** (`/feed/`) | No (Public) | Standard web rate limits | Every 60–120 min | **High (5/5)** | **Selected for Phase 1A (Source 2)** |
| **Smart India Hackathon (SIH)** | Government / Hackathons | Official Government Portal | No | No | No (Public) | Polite crawling (5s delay) | Every 3–6 hours | **High (4/5)** | **Selected for Phase 1A (Source 3)** |
| **Python Software Foundation** | Education / Fellowships | Official Atom Feed | No | **Yes** (Blogspot Atom) | No (Public) | Standard web rate limits | Every 2–4 hours | **High (4/5)** | Evaluated (Alternative feed) |
| **Kaggle** | AI / Machine Learning | CLI / API Token | Yes | No | **Yes** (API Key required) | 1 req/sec | Every 60–120 min | **High (4/5)** | Postponed to Phase 1B (requires user token) |
| **Devfolio** | Hackathons | Internal Web API | No public REST API | No official RSS | HTTP 422 without session headers | Undocumented | Every 60 min | **Medium (3/5)** | Postponed to Phase 1B (needs custom headers) |
| **AICTE India** | Government / Engineering | HTML Portal (`aicte.gov.in`) | No | No | No (Public) | Polite crawling | Every 6–12 hours | **Medium (3/5)** | Postponed (Migrated domain, heavy SPA layout) |
| **MyGov Innovate** | Government / Challenges | HTML / WP Feed | No | Yes (currently empty) | No (Public) | Polite crawling | Every 6–12 hours | **Medium (3/5)** | Postponed (RSS feed empty in current cycle) |

---

## 2. Selected Phase 1A Sources

### 2.1 Source 1: Codeforces (Competitive Programming)
* **Official URL**: `https://codeforces.com`
* **Endpoint**: `https://codeforces.com/api/contest.list?gym=false`
* **Access Method**: Official REST API returning JSON.
* **Payload Structure**:
  ```json
  {
    "status": "OK",
    "result": [
      {
        "id": 2261,
        "name": "Codeforces Round (Div. 1 + Div. 2)",
        "type": "CF",
        "phase": "BEFORE",
        "durationSeconds": 10800,
        "startTimeSeconds": 1792247700,
        "relativeTimeSeconds": -3184409
      }
    ]
  }
  ```
* **Extracted Fields**: Contest ID (`external_id`), Contest Name, Phase (`BEFORE`, `FINISHED`), Start Time (`startTimeSeconds`), Duration (`durationSeconds`), Canonical URL (`https://codeforces.com/contest/{id}`).
* **Incremental Strategy**: Track contests where `phase == "BEFORE"` or `relativeTimeSeconds < 0` to discover upcoming rounds.

### 2.2 Source 2: GitHub Tech Blog (Company Tech Programs & Initiatives)
* **Official URL**: `https://github.blog`
* **Endpoint**: `https://github.blog/feed/`
* **Access Method**: Official RSS 2.0 XML Feed.
* **Payload Structure**: Standard XML `<rss><channel><item>...</item></channel></rss>`.
* **Extracted Fields**: Article Title (`<title>`), Canonical URL (`<link>`), Publication Timestamp (`<pubDate>`), GUID (`<guid>`), Summary (`<description>`), Full Text (`<content:encoded>`).
* **Incremental Strategy**: Track `<guid>` and `<pubDate>`. Stop processing once a previously recorded `<guid>` is reached.

### 2.3 Source 3: Smart India Hackathon (Government Innovation Challenges)
* **Official URL**: `https://sih.gov.in`
* **Endpoint**: `https://sih.gov.in/sih2026PS`
* **Access Method**: Official Government Web Portal (HTML parsing).
* **Payload Structure**: Problem statements table/cards with titles, organization IDs, categories (Software/Hardware), and descriptions.
* **Extracted Fields**: Problem statement title, host ministry/department, category, problem ID, and guideline portal links.
* **Incremental Strategy**: Content hashing of problem statement titles and descriptions.
