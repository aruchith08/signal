# SIGNAL 📡 — Notification Decision Engine & Anti-Fatigue System

## 1. Overview

The **Notification Decision Engine** prevents alert fatigue while ensuring high-value updates reach users reliably and on time. 

Every potential alert passes through a 10-step evaluation pipeline before a message is allowed to dispatch.

---

## 2. 10-Step Decision Flow

```text
NEW OPPORTUNITY / LIFECYCLE EVENT
        ↓
1. USER ACTIVE? (user.is_active)
        ↓
2. NOTIFICATIONS ENABLED? (preferences.enabled)
        ↓
3. PERSONALIZATION & RELEVANCE EVALUATION (PersonalizationEngine)
        ↓
4. RELEVANCE ABOVE THRESHOLD? (relevance.score >= preferences.min_relevance_score)
        ↓
5. ACADEMIC ELIGIBILITY CHECK (relevance.eligibility_status != INELIGIBLE)
        ↓
6. ACTIONABLE EVENT GATE (NotificationDeduplicator.is_actionable_event)
        ↓
7. DEDUPLICATION CHECK (NotificationDeduplicator.is_duplicate)
        ↓
8. PRIORITY ESCALATION (PriorityEscalator.escalate)
        ↓
9. THROTTLING & QUIET HOURS (NotificationThrottler.evaluate_throttling)
        ↓
10. FINAL DELIVERY DECISION (INSTANT / QUEUED / DIGEST / SKIPPED)
```

---

## 3. Anti-Fatigue & Throttling Rules

### 3.1 Strict Deduplication
- **Exact Tuple Check**: `(user_id, opportunity_id, event_id)`. If an alert has already been delivered, queued, or sent for this exact event, it is skipped.
- **Opportunity Cooldown**: Non-critical updates for the same opportunity within a 12-hour window are suppressed.

### 3.2 Daily Rate Limiting
- Configurable per user (`max_alerts_per_day`, default: 10).
- Counts notifications delivered since midnight local time in the user's timezone.
- Excess alerts are marked as `SKIPPED` unless they are `CRITICAL` priority and `SIGNAL_CRITICAL_ALERT_BYPASS_RATE_LIMIT=true`.

### 3.3 Timezone-Aware Quiet Hours
- Configurable window (e.g. `22:30` → `07:30`).
- Supports windows spanning midnight.
- When an alert triggers during quiet hours:
  - `CRITICAL` alerts bypass quiet hours if `SIGNAL_CRITICAL_ALERT_BYPASS_QUIET_HOURS=true`.
  - Non-critical alerts are marked `QUEUED` with `scheduled_for` set to the morning expiration of quiet hours.

---

## 4. Priority Escalation & Deadline Urgency

Urgency is evaluated based on hours remaining until the event deadline:

| Time Remaining | Urgency Level | Escalation Behavior |
| :--- | :--- | :--- |
| $< 6$ hours | `EXTREME` | Escalates to `CRITICAL` if relevance $\ge 65$. |
| $< 24$ hours | `CRITICAL` | Escalates to `CRITICAL` if relevance $\ge 65$. |
| $< 3$ days | `HIGH` | Escalates to `HIGH` if relevance $\ge 70$. |
| $< 7$ days | `MEDIUM` | Standard delivery priority. |
| $\ge 7$ days | `NORMAL` | Standard delivery priority. |

In addition, critical lifecycle events (`registration_closing`, `application_deadline`, `deadline_extended`) on watched programs automatically escalate to `CRITICAL`.

---

## 5. Audit Trail & Database Persistence

Every decision is permanently recorded in the `notifications` table:

- `user_id` & `opportunity_id` & `event_id`
- `channel`: `telegram`, `mock`, `email`
- `priority`: `critical`, `high`, `medium`, `low`
- `status`: `pending`, `queued`, `sent`, `delivered`, `failed`, `skipped`
- `delivery_mode`: `instant`, `digest`, `queued`, `skipped`
- `relevance_score`: Float
- `decision_reason`: Detailed explanation of decision
- `sent_at` & `delivered_at`: UTC timestamps
- `error_message`: Failure exception trace if provider errors
