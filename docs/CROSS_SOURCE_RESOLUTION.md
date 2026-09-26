# SIGNAL 📡 — Cross-Source Entity Resolution

## 1. Objective
Cross-source resolution determines whether two announcements from disparate internet sources (e.g., official company portal vs. Unstop vs. news release) describe the same real-world opportunity.

## 2. 4-Stage Matching Hierarchy

### Level 1: Exact Match (Confidence: 1.00)
- **External ID**: Match against historical `RawDiscovery.external_id`.
- **Canonical Application URL**: Normalized URL match stripping tracking queries (`utm_*`, `ref`).
- **Exact Name + Organization + Year**: Normalized alphanumeric string equality within identical organizations.
- **Action**: Automatic merge.

### Level 2: Strong Deterministic Match (Confidence: 0.90 – 0.99)
- **Conditions**:
  - Identical organization.
  - Compatible year/season.
  - Discriminative token containment (e.g. "TCS CodeVita" within "TCS CodeVita Season 13 Registration").
  - Non-discriminative stop words removed.
- **Action**: Automatic merge.

### Level 3: Heuristic Match (Confidence: 0.75 – 0.89)
- **Conditions**:
  - Match against curated or extracted `OpportunityAlias` records.
  - Compatible dates and category.
- **Action**: Auto-merge if verified; otherwise promote to candidate.

### Level 4: Semantic Similarity Match (Confidence: 0.60 – 0.89)
- **Conditions**:
  - Cosine similarity on dense embedding vectors generated from invariant text representations.
- **Action**: **NEVER** merged automatically. Generated as a `SemanticMatchCandidate` for verification.
