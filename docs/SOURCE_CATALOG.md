# SIGNAL 📡 — Monitored Source Catalog

This document provides a comprehensive catalog of all monitored and planned opportunity sources within SIGNAL.

---

## 1. Catalog Schema

Every source is cataloged with the following parameters:
- **Source Name**: Official public brand or initiative name.
- **Organization**: Authoritative host organization.
- **Category**: Domain classification (`COMPETITIVE_PROGRAMMING`, `HACKATHON`, `OPEN_SOURCE_PROGRAM`, `GOVERNMENT`, `MAJOR_COMPANY_PROGRAM`, etc.).
- **Official URL**: Primary web destination.
- **Source Type**: Ingestion protocol (`REST_API`, `GRAPHQL`, `JSON_FEED`, `RSS`, `OFFICIAL_WEBSITE`).
- **Connector**: Implemented connector class.
- **Polling Policy**: Polling frequency tier (`HIGH_PRIORITY`, `MEDIUM_PRIORITY`, `LOW_PRIORITY`, `ARCHIVAL`).
- **Trust Tier**: Source credibility (`HIGHEST`, `HIGH`, `MEDIUM_HIGH`, `MEDIUM`).
- **Status**: Operational availability (`HEALTHY`, `DEGRADED`, `FAILING`, `DISABLED`).
- **Supported Data**: Specific fields extracted.
- **Limitations**: Rate limits, scraping caveats, or network requirements.

---

## 2. Active Verified Sources

### Codeforces
- **Organization**: Codeforces
- **Category**: `COMPETITIVE_PROGRAMMING`
- **Official URL**: `https://codeforces.com`
- **Source Type**: `REST_API` (`https://codeforces.com/api/contest.list?gym=false`)
- **Connector**: `CodeforcesConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGHEST`
- **Status**: `HEALTHY`
- **Supported Data**: Contest ID, name, division, start time, duration, phase.
- **Limitations**: Rate limited to 1 request per 2 seconds.

---

### CodeChef
- **Organization**: CodeChef
- **Category**: `COMPETITIVE_PROGRAMMING`
- **Official URL**: `https://www.codechef.com`
- **Source Type**: `REST_API` (`https://www.codechef.com/api/list/contests/all`)
- **Connector**: `CodeChefConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGH`
- **Status**: `HEALTHY`
- **Supported Data**: Contest code, contest name, start date ISO, end date ISO, duration.
- **Limitations**: Public upcoming and present contest list.

---

### HackerRank
- **Organization**: HackerRank
- **Category**: `COMPETITIVE_PROGRAMMING`
- **Official URL**: `https://www.hackerrank.com`
- **Source Type**: `REST_API` (`https://www.hackerrank.com/rest/contests/upcoming`)
- **Connector**: `HackerRankConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGH`
- **Status**: `HEALTHY`
- **Supported Data**: Contest slug, title, epoch start time, epoch end time, contest description.
- **Limitations**: Only public upcoming contest models returned without authentication.

---

### LeetCode
- **Organization**: LeetCode
- **Category**: `COMPETITIVE_PROGRAMMING`
- **Official URL**: `https://leetcode.com`
- **Source Type**: `API` (GraphQL: `https://leetcode.com/graphql`)
- **Connector**: `LeetCodeConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGH`
- **Status**: `HEALTHY`
- **Supported Data**: Contest title, title slug, start timestamp, duration in seconds.
- **Limitations**: GraphQL public contest query. Requires POST with JSON payload.

---

### Google Summer of Code / Open Source
- **Organization**: Google
- **Category**: `OPEN_SOURCE_PROGRAM`
- **Official URL**: `https://opensource.googleblog.com`
- **Source Type**: `JSON_FEED` (`https://opensource.googleblog.com/feeds/posts/default?alt=json`)
- **Connector**: `GSoCConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGHEST`
- **Status**: `HEALTHY`
- **Supported Data**: Post title, published timestamp, author, full HTML body, direct URL.
- **Limitations**: Blog feed mixes GSoC announcements with technical engineering posts (filtered deterministically).

---

### Smart India Hackathon
- **Organization**: Ministry of Education & AICTE
- **Category**: `HACKATHON`
- **Official URL**: `https://sih.gov.in`
- **Source Type**: `OFFICIAL_WEBSITE` (`https://sih.gov.in/sih2026PS`)
- **Connector**: `SIHConnector`
- **Polling Policy**: `HIGH_PRIORITY` (Every 30 mins)
- **Trust Tier**: `HIGHEST`
- **Status**: `HEALTHY`
- **Supported Data**: Problem statement ID, title, organization, category, description modal.
- **Limitations**: HTML table parsing; updates during national SIH cycles.

---

### MyGov Innovate
- **Organization**: Government of India
- **Category**: `GOVERNMENT`
- **Official URL**: `https://innovateindia.mygov.in`
- **Source Type**: `OFFICIAL_WEBSITE` (`https://innovateindia.mygov.in/`)
- **Connector**: `MyGovConnector`
- **Polling Policy**: `MEDIUM_PRIORITY` (Every 2 hours)
- **Trust Tier**: `HIGHEST`
- **Status**: `HEALTHY`
- **Supported Data**: Initiative name, details, application deadline, portal link.
- **Limitations**: HTML anchor card extraction.

---

### Major League Hacking (MLH)
- **Organization**: Major League Hacking
- **Category**: `HACKATHON`
- **Official URL**: `https://mlh.io`
- **Source Type**: `OFFICIAL_WEBSITE` (`https://mlh.io/seasons/2026/events`)
- **Connector**: `MLHConnector`
- **Polling Policy**: `MEDIUM_PRIORITY` (Every 2 hours)
- **Trust Tier**: `HIGH`
- **Status**: `HEALTHY`
- **Supported Data**: Hackathon title, date range, location, official event URL.
- **Limitations**: HTML parsing of seasonal calendar.

---

### GitHub Engineering Blog
- **Organization**: GitHub
- **Category**: `MAJOR_COMPANY_PROGRAM`
- **Official URL**: `https://github.blog`
- **Source Type**: `RSS` (`https://github.blog/feed/`)
- **Connector**: `GitHubBlogConnector`
- **Polling Policy**: `LOW_PRIORITY` (Every 6 hours)
- **Trust Tier**: `HIGH`
- **Status**: `HEALTHY`
- **Supported Data**: Post title, published timestamp, author, RSS HTML summary.
- **Limitations**: Mostly technical articles and service post-mortems (audited and filtered).

---

## 3. Catalogued Sources (Future Work & Known Limitations)

| Source Name | Category | Official URL | Reason Not Implemented in Phase 1C |
| :--- | :--- | :--- | :--- |
| **Devfolio** | Hackathons | `https://devfolio.co/hackathons` | Public API requests are intercepted by Cloudflare anti-bot verification or time out without full browser environment. |
| **MeitY What's New** | Government | `https://www.meity.gov.in/whatsnew` | Portal is built as a Next.js client-side Single Page Application (SPA); server response contains minimal hydration shell without SSR content. |
| **AICTE Announcements** | Government | `https://www.aicte-india.org` | Dedicated announcements endpoint `/announcements` returns HTTP 404; notifications require interactive portal navigation. |
| **Kaggle Competitions** | AI/ML | `https://www.kaggle.com` | Official REST API requires API key authentication and Bearer tokens; public scraping is Cloudflare protected. |
