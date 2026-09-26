# SIGNAL 📡 — Structured Opportunity Change Intelligence

## 1. Overview

While snapshot change detection filters HTML noise at the source level, **Opportunity Structured Change Intelligence** tracks granular, field-level modifications when an existing canonical `Opportunity` is updated with newly ingested data.

This provides:
1. **Auditability**: Complete chronological record of every deadline shift, status transition, and link update.
2. **Idempotency**: Prevents repeated ingestion runs from flooding the database with duplicate change events.
3. **Targeted Notifications**: Supplies prioritized `ChangeSet` signals to downstream alerting pipelines.

---

## 2. Monitored Fields & Priority Mapping

`OpportunityChangeDetector` monitors high-value fields and maps them to domain `ChangeType` and `PriorityLevel`:

| Field Name | Change Type | Priority | Semantic Meaning |
| :--- | :--- | :--- | :--- |
| `deadline_date` | `DEADLINE_CHANGED` | `CRITICAL` | Deadline extended, shortened, or announced |
| `current_state` | `STATUS_CHANGED` / `DEADLINE_CHANGED` | `HIGH` / `CRITICAL` | Transition in event status (e.g. registration opened) |
| `status` | `STATUS_CHANGED` | `HIGH` | Opportunity status changes (active, closed, archived) |
| `eligibility` | `CONTENT_CHANGED` | `MEDIUM` | Updates to candidate criteria or target audience |
| `application_url` | `CONTENT_CHANGED` | `MEDIUM` | Submission link updates or migrations |
| `title` | `CONTENT_CHANGED` | `LOW` | Cosmetic title corrections |
| `season` / `year` | `CONTENT_CHANGED` | `LOW` | Edition and annual cycle tracking |

---

## 3. Order of Operations

Change detection **strictly occurs before** existing `Opportunity` fields are overwritten:

```text
Discovery Ingestion
        ↓
Entity Resolution Match Found
        ↓
Extract Normalized Candidate Values
        ↓
OpportunityChangeDetector.detect_and_record(...)
  ├── Check: existing_opp is None? → Return [] (0 changes on initial creation)
  ├── Natural value comparison: (old_str == new_str? → Skip)
  ├── Intra-session duplicate guard (session.new)
  ├── Database duplicate guard (query existing ChangeSet)
  └── session.add(ChangeSet(previous_value, new_value, change_type, importance))
        ↓
Mutate Opportunity Model with New Values
        ↓
db.flush() / db.commit()
```

---

## 4. Duplicate Prevention Strategy

To ensure zero phantom changes across recurring ingestion runs:
1. **Natural Equality Comparison**: If string representations match or both are null, no `ChangeSet` is created.
2. **Active Session Guard**: Scans pending uncommitted `ChangeSet` objects in `session.new` to eliminate intra-transaction duplication.
3. **Database Idempotency Check**: Queries `change_sets` table for existing matching `(opportunity_id, field_name, previous_value, new_value)` rows before persisting.
