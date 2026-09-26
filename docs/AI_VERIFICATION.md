# SIGNAL 📡 — AI Verification & Cost Control

## 1. Overview
SIGNAL uses deterministic systems wherever possible. AI is invoked **strictly as an escalation mechanism** for:
- Candidates with confidence between $0.70$ and $0.90$.
- Cases where semantic similarity is high but deterministic token evidence is ambiguous.
- Irreconcilable source conflict analysis.

## 2. Structured Verification Schema
The AI provider must return strict JSON validated via Pydantic:
```json
{
  "same_opportunity": true,
  "confidence": 0.94,
  "reason": "Both announcements describe TCS CodeVita 2026",
  "conflicts": [],
  "recommended_action": "MERGE"
}
```

## 3. Cost & Quota Controls (`AIUsagePolicy`)
- `MAX_AI_VERIFICATION_CALLS_PER_RUN`: Default capped at 20 calls.
- Telemetry: Tracks task, provider, duration, success/failure status, and estimated tokens.
- Budget Exhaustion Safeguard: When the quota is reached, remaining candidates are transitioned to `REVIEW` status for human review rather than silently skipped.
