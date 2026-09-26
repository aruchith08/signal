# SIGNAL 📡 — Telegram Alert & Bot Integration

## 1. Overview

SIGNAL integrates with Telegram using the Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/sendMessage`).

The Telegram provider operates in two modes:
1. **Live Telegram Delivery**: When `TELEGRAM_BOT_TOKEN` is configured and `SIGNAL_NOTIFICATION_PROVIDER=telegram`.
2. **Mock Notifier**: Default development mode. In-memory logging with 0 external network dependencies and complete test isolation.

---

## 2. Environment Configuration

Add the following variables to `.env`:

```env
# Telegram Bot Token (obtain from @BotFather)
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"

# Default fallback chat ID if user profile lacks chat_id
TELEGRAM_DEFAULT_CHAT_ID="987654321"

# Active Provider: "telegram" or "mock"
SIGNAL_NOTIFICATION_PROVIDER="mock"

# Thresholds and Throttling
SIGNAL_DEFAULT_MIN_RELEVANCE_SCORE=70
SIGNAL_DEFAULT_DAILY_NOTIFICATION_LIMIT=10
SIGNAL_CRITICAL_ALERT_BYPASS_QUIET_HOURS=true
SIGNAL_CRITICAL_ALERT_BYPASS_RATE_LIMIT=true
```

---

## 3. Telegram Bot Commands

| Command | Action | Output / Behavior |
| :--- | :--- | :--- |
| `/start` | Onboarding & account linking | Welcomes user, detects chat ID, creates subscriber profile if new. |
| `/status` | Status inquiry | Returns notification status (Enabled/Paused), threshold score, chat ID, and active interests. |
| `/preferences` | View settings | Displays quiet hours, digest preference, and daily limits. |
| `/subscribe` | Enable alerts | Sets `preferences.enabled = True`. |
| `/unsubscribe` | Pause alerts | Sets `preferences.enabled = False` without deleting the user. |
| `/help` | Command directory | Lists available bot commands. |

---

## 4. Message Formatting

Alerts are formatted in Markdown with proper character escaping (`_*` `[`):

```text
🚨 SIGNAL ALERT

🔥 TCS CodeVita Season 13
📌 Registrations are now open

🎯 Relevance: 96%

Why you're seeing this:
• Program Watch hit: 'TCS CodeVita' is an actively monitored program
• Matches your interest in Competitive Programming
• Matches your skills: Python, C++

⏰ Deadline:
25 October 2026, 18:30 UTC

🏢 Organization:
Tata Consultancy Services

🔗 [Apply / Learn More](https://codevita.tcsapps.com)

📡 SIGNAL Opportunity Network
```

---

## 5. Webhook Integration

The FastAPI endpoint `POST /api/v1/notifications/telegram/webhook` handles incoming Telegram updates.

To register your live webhook with Telegram:
```bash
curl -F "url=https://your-domain.com/api/v1/notifications/telegram/webhook" https://api.telegram.org/bot<TOKEN>/setWebhook
```
