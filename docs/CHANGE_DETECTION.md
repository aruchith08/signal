# SIGNAL 📡 — Semantic Change Detection & Meaningful Filtering

## 1. Overview

Websites update frequently, but the majority of edits are cosmetic noise (timestamps, visitor counts, cookie banners, navigation layout changes). Conversely, critical updates—such as registration opening, deadlines shifting, or problem statements being released—frequently occur on the **same existing URL**.

SIGNAL employs a two-tier **Semantic Change Detection Engine** to differentiate between cosmetic updates and actionable opportunity lifecycle transitions.

---

## 2. Noise Normalization & Hashing

Before comparison, content passes through `MeaningfulChangeDetector.normalize_for_comparison()`:

```text
RAW HTML / PAYLOAD
        ↓
STRIP VOLATILE PATTERNS
(Timestamps, "Last updated at ...", Page view counts, Cookie notices)
        ↓
COLLAPSE WHITESPACE & LOWERCASE
        ↓
COMPUTE HASHES
- content_hash: SHA256 of raw response (detects byte-level modifications)
- snapshot_hash: SHA256 of normalized text (detects semantic modifications)
```

### Ignored Noise Patterns:
- `Last updated at 10:01 AM on 12/09/2026`
- `Current server time: ...`
- `Page views: 1,420`
- `Visitors online: ...`
- `Accept cookies to continue / Cookie Policy`
- Header / footer navigation whitespace and formatting shifts

---

## 3. Meaningful Change Evaluation

When the snapshot hash changes, `MeaningfulChangeDetector` evaluates the semantic delta:

| Change Type | Trigger Condition | Pipeline Action |
| :--- | :--- | :--- |
| `NO_CHANGE` | Normalized text and item counts are identical. | Suppressed from creating duplicate events. |
| `NEW_ITEM` | Item count increased compared to previous snapshot. | Process new candidate discoveries. |
| `ITEM_REMOVED` | Item count decreased (items expired or archived). | Log audit record in snapshot. |
| `STATUS_CHANGED` | Lifecycle phrases appeared (*"registrations open"*, *"results announced"*). | Update Opportunity `current_state` and create `OpportunityEvent`. |
| `DEADLINE_CHANGED` | Deadline date shifted earlier or later. | Trigger `DeadlineEvaluator` for timeline tracking. |
| `CONTENT_CHANGED` | Substantial text change (>50 characters) detected. | Process discovery update. |

---

## 4. Date Extraction & Deadline Intelligence

`services/intelligence/date_extraction.py` parses multi-format date strings into timezone-aware `datetime` values while preserving the original string:

### Supported Formats:
- Day-Month-Year: `15th September 2026`, `15-Sep-2026`
- Month-Day-Year: `September 20, 2026`, `Sep 20 2026`
- ISO 8601: `2026-10-31`
- Slash Format: `10/09/2026`

### Deadline Evaluation Rules:
1. **`DEADLINE_ANNOUNCED`**:
   - Condition: Opportunity had no prior deadline; a valid deadline date was parsed.
   - Lifecycle Event: `registration_deadline` recorded.
2. **`DEADLINE_EXTENDED`**:
   - Condition: New deadline date is strictly greater than the previous deadline (`new_date > old_date`).
   - Lifecycle Event: `DEADLINE_EXTENDED` event logged with explainable reason.
3. **`DEADLINE_SHORTENED`**:
   - Condition: New deadline date is earlier than the previous deadline (`new_date < old_date`).
   - Lifecycle Event: `DEADLINE_SHORTENED` event logged.
