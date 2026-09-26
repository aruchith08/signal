# SIGNAL 📡 — Semantic Similarity Engine

## 1. Overview
The semantic matching subsystem detects conceptually identical opportunities whose titles or phrasing differ (e.g., *"Google Summer of Code"* vs *"GSoC Student Contributor Program"*).

## 2. Invariant Text Strategy
Embeddings must not fluctuate based on ephemeral announcement details. `SemanticMatcher.build_invariant_text()` normalizes inputs by extracting:
- Opportunity Title
- Organization Name
- Broad Category
- Year & Season
- Core Description (stripping volatile dates and URLs)

## 3. Pluggable Embedding Architecture
- `EmbeddingProvider`: Abstract base class.
- `MockEmbeddingProvider`: Deterministic 64-dimensional n-gram token hashing vectorizer with L2 normalization. Default for zero-cost testing and offline development.
- `NvidiaEmbeddingProvider`: Connects to NVIDIA NIM embedding endpoints when `NVIDIA_API_KEY` is provided.

## 4. Candidate Rule
Semantic similarity scores $\ge 0.65$ generate `SemanticMatchCandidate` records. They are **never** auto-merged on embeddings alone, preventing false merges.
