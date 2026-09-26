# SIGNAL 📡 — Personalization & Relevance Intelligence

## 1. Overview

SIGNAL transforms raw, unranked opportunity streams into a personalized intelligence feed tailored to each student and developer. 

Rather than relying on non-deterministic cloud LLMs, the **Personalization & Relevance Engine** uses a deterministic scoring and rule-based evaluation architecture that executes in sub-millisecond timeframes, guarantees explainability, and incurs zero API cost.

---

## 2. User Intelligence Domain Model

The user intelligence system is built on four normalized sub-models:

```text
User
│
├── Basic Profile (users table)
│     ├── email
│     ├── username
│     ├── full_name
│     └── is_active
│
├── Academic & Career Profile (user_profiles table)
│     ├── education_level (Undergraduate / Postgraduate / Doctoral)
│     ├── degree (B.Tech / MCA / M.Tech / PhD)
│     ├── branch (Computer Science, Electrical, etc.)
│     ├── current_year (1, 2, 3, 4)
│     ├── graduation_year (2025, 2026, 2027)
│     ├── country (India / Global)
│     ├── timezone (Asia/Kolkata / UTC)
│     ├── career_interests (Software Engineering, AI/ML, Cloud)
│     └── preferred_opportunity_types (competitive_programming, hackathon)
│
├── Weighted Interests (user_interests table)
│     └── category + tag + weight (0.0 → 1.0)
│
├── User Skills (user_skills & skills tables)
│     └── skill_name + proficiency_level (beginner / intermediate / advanced / expert)
│
└── Notification Preferences (user_notification_preferences table)
      ├── enabled (bool)
      ├── min_relevance_score (0 – 100, default 70)
      ├── instant_alerts_enabled (bool)
      ├── digest_enabled (bool)
      ├── quiet_hours_enabled (bool)
      ├── quiet_hours_start ("22:30")
      ├── quiet_hours_end ("07:30")
      ├── max_alerts_per_day (default 10)
      └── telegram_chat_id, telegram_user_id, telegram_username
```

---

## 3. Weighted Interests

User interests are not binary flags; they carry floating-point weights from `0.0` to `1.0`:

```text
Interest Categories:
• AI_ML (e.g. weight 1.0)
• COMPETITIVE_PROGRAMMING (e.g. weight 0.95)
• HACKATHONS (e.g. weight 0.90)
• OPEN_SOURCE (e.g. weight 0.80)
• SOFTWARE_ENGINEERING (e.g. weight 0.90)
• INTERNSHIPS (e.g. weight 0.85)
• SCHOLARSHIPS (e.g. weight 0.70)
• RESEARCH (e.g. weight 0.60)
• GOVERNMENT_PROGRAMS (e.g. weight 0.75)
• STARTUPS (e.g. weight 0.65)
```

Interest score contribution scales directly with `weight * 30.0` points.

---

## 4. Deterministic Relevance Scoring (0 – 100)

The scoring engine evaluates six discrete components:

| Component | Max Points | Description |
| :--- | :--- | :--- |
| **Interest Match** | 0 – 30 | Evaluates category & tag alignment against user's weighted interests. Formula: $\text{weight} \times 30.0$. |
| **Category Match** | 0 – 15 | Direct alignment with user's preferred opportunity types or profile category. |
| **Skill Match** | 0 – 15 | Intersection of user skills with opportunity required skills, tags, or description. 1 match = 10 pts, $\ge 2$ matches = 15 pts. |
| **Academic Eligibility** | 0 – 15 | Evaluated by `EligibilityEvaluator`: `ELIGIBLE` = 15, `LIKELY_ELIGIBLE` = 10, `UNKNOWN` = 5, `INELIGIBLE` = 0. |
| **Program Watch Match** | 0 – 15 | Triggered if the opportunity was matched by the Program Watch Engine. Formula: $\text{watch\_match\_score} \times 15.0$. |
| **Opportunity Priority** | 0 – 10 | Opportunity base priority: `CRITICAL` = 10, `HIGH` = 7, `MEDIUM` = 4, `LOW` = 1. |

$$\text{Total Score} = \min\left(100, \max\left(0, \sum \text{Component Scores}\right)\right)$$

### Ineligibility Safety Guard:
If the user is classified as `INELIGIBLE` by the academic eligibility evaluator, the final score is strictly capped at **25/100**, preventing unwanted alerts.

---

## 5. Academic Eligibility Evaluator

The `EligibilityEvaluator` implements conservative eligibility matching:

* **Degrees & Levels**:
  * Undergraduates: `B.Tech`, `B.E.`, `BCA`, `B.Sc.`
  * Postgraduates: `M.Tech`, `MCA`, `M.Sc.`
  * Doctoral: `PhD`, `Doctorate`
* **Exclusions**: Explicit keywords (`Only PhD`, `Only Master's`, `Only 2024 batch`) result in `INELIGIBLE` if the user's profile conflicts.
* **Inclusions**: Degree matches produce `ELIGIBLE`.
* **Conservative Fallback**: If criteria are unspecified, the system returns `UNKNOWN` (5 points) or `LIKELY_ELIGIBLE` (10 points). It **never** falsely claims `INELIGIBLE` or `ELIGIBLE` without evidence.

---

## 6. Explainability System

Every relevance result produces human-readable explanation bullet points:

```json
{
  "score": 96,
  "confidence": 0.98,
  "eligibility_status": "eligible",
  "reasons": [
    "Program Watch hit: 'TCS CodeVita' is an actively monitored program",
    "Matches your interest in Competitive Programming",
    "Matches your skills: Python, C++",
    "Opportunity priority is CRITICAL",
    "Eligible: Matches undergraduate requirements"
  ],
  "matched_interests": ["competitive_programming"],
  "matched_skills": ["python", "c++"],
  "matched_programs": ["TCS CodeVita"],
  "component_scores": {
    "interest_match": 30.0,
    "category_match": 15.0,
    "skill_match": 15.0,
    "academic_eligibility": 15.0,
    "program_watch_match": 15.0,
    "opportunity_priority": 10.0
  }
}
```
