# SIGNAL 📡 — Phase 3: Verification & Consensus Architecture

## 1. Overview
The **Verification & Consensus Subsystem** in SIGNAL elevates the platform from single-source observation to **authoritative multi-source intelligence**. When opportunities, hackathons, coding contests, and fellowships are announced across the internet, they frequently surface on multiple platforms with varying degrees of accuracy, timing, and detail.

SIGNAL coordinates cross-source evidence to:
1. Map multiple independent announcements to **one trusted canonical opportunity**.
2. Score source authenticity based on an objective **trust hierarchy**.
3. Conservatively prevent **false merges** using strict guardrails.
4. Verify individual facts (deadlines, URLs, eligibility) at the attribute level.
5. Record source conflicts transparently without data loss.
6. Escalate ambiguous candidates to **AI verification** and human review queues.

---

## 2. Layered Pipeline Architecture

```text
EXTERNAL INTERNET SOURCES (APIs, Feeds, Portals)
                     ↓
             RAW DISCOVERIES
                     ↓
             DOMAIN CLASSIFIER
                     ↓
        CROSS-SOURCE ENTITY RESOLVER
  ├── Level 1: Exact Match (ID, Canonical URL, Name + Org + Year) [1.00]
  ├── Level 2: Strong Deterministic Token Containment [0.90 - 0.99]
  ├── Level 3: Heuristic Match (Aliases, Proximate Dates) [0.75 - 0.89]
  └── Level 4: Semantic Similarity (Embedding Cosine Match) [0.60 - 0.89]
                     ↓
             MERGE GUARDRAILS
  (Stops Org conflicts, Year conflicts, Season conflicts, Incompatible categories)
                     ↓
          IS CANDIDATE AMBIGUOUS?
                     ├── YES ──► AI VERIFICATION ──► HUMAN REVIEW QUEUE
                     └── NO
                     ↓
             VERIFICATION ENGINE
  ├── Source Trust Scoring (Government > Organization > Platform > News)
  ├── Fact-Level Consensus (Official sources dominate, consensus voting)
  └── Conflict Detection (Deadlines, eligibility, URLs, seasons)
                     ↓
         CANONICAL OPPORTUNITY STORE
  (verification_status, confidence, source_count, official_present)
                     ↓
         PERSONALIZATION & TELEGRAM ALERTS
```

---

## 3. Data Models
- **`OpportunitySource`**: Tracks every URL, discovery, trust score, and official flag contributing to an opportunity.
- **`VerifiedField`**: Fact-level attribute verification with source counts and official confirmation flags.
- **`VerificationConflict`**: Structured records of field-level discrepancies between contributing platforms.
- **`SemanticMatchCandidate`**: Pairs evaluated via embeddings and heuristics.
- **`VerificationReview`**: Human-in-the-loop review queue for ambiguous mergers or unresolved conflicts.
