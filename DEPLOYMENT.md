# SIGNAL 📡 — Production Deployment & Operational Runbook

This guide covers real-world production deployment of the **SIGNAL 📡 Opportunity Intelligence Platform**.

SIGNAL is designed as a **lean, deterministic-first modular monolith** powered by FastAPI, SQLAlchemy 2.0 Async, Alembic, and PostgreSQL. It requires **strictly zero external brokers** (no Kafka, Redis, ZooKeeper, or vector databases).

---

## 1. Architecture Overview

```
[ Ingestion Network ] ──> [ Resilient HTTP Client / Bounded Pagination ]
                                    │
                                    ▼
[ Distributed Lock (PostgreSQL) ] ──> [ Idempotent Ingestion Pipeline ]
                                    │
                                    ▼
                          [ Domain Classifier ] ──> Pattern Matching (<1ms)
                                    │               (Fallback: AI Gateway)
                                    ▼
                          [ Entity Resolver ] ───> Token-Filtered Matching
                                    │
                                    ▼
                         [ Opportunity Lifecycle ] ──> State Machine & Deadlines
                                    │
                                    ▼
                       [ Personalization Scorer ] ──> Explainable Fit (0-100)
                                    │
                                    ▼
                      [ Notification Dispatcher ] ──> Telegram, Discord,
                                    │                 Email, In-App
                                    ▼
                        [ User Interface SPA ] ────> React 18 / Static Serving
```

---

## 2. Configuration & Secrets

All configuration parameters must be supplied via environment variables (or `.env` file). Never commit sensitive credentials to source control.

| Environment Variable | Required | Default / Format | Description |
|----------------------|----------|-------------------|-------------|
| `DATABASE_URL` | **Yes** | `postgresql+asyncpg://user:pass@host:5432/dbname` | Async PostgreSQL connection string |
| `JWT_SECRET_KEY` | **Yes** | (min 32 random characters) | Cryptographic signing key for JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| No | `1440` (24h) | JWT access token lifespan in minutes |
| `ENVIRONMENT` | No | `production` | Deployment mode (`production`/`development`) |
| `DEBUG` | No | `False` | Verbose debug flag |
| `HOST` | No | `0.0.0.0` | Bind host address |
| `PORT` | No | `8000` | Bind port number |
| `CORS_ORIGINS` | **Yes** | `https://signal.domain.com` | Comma-separated allowed CORS origins |
| `AI_PRIMARY_PROVIDER` | No | `mock` / `ollama` / `openai` / `gemini` | Primary AI Gateway provider |
| `AI_FALLBACK_PROVIDER` | No | `mock` | Fallback classification provider |
| `TELEGRAM_BOT_TOKEN` | Optional | `123456:ABC-DEF...` | Telegram Bot API token for dispatch |
| `TELEGRAM_DEFAULT_CHAT_ID` | Optional | `-100...` | Default Telegram broadcast chat/channel ID |
| `DISCORD_WEBHOOK_URL`| Optional | `https://discord.com/api/webhooks/...` | Discord webhook URL for rich alerts |
| `SMTP_HOST` | Optional | `smtp.example.com` | SMTP outgoing host for email notifications |
| `SMTP_PORT` | Optional | `587` | SMTP port (587 for TLS, 465 for SSL) |
| `SMTP_USERNAME` | Optional | `user@example.com` | SMTP authentication user |
| `SMTP_PASSWORD` | Optional | `secret` | SMTP authentication password |
| `SMTP_FROM` | Optional | `alerts@signal.dev` | `From` address header for notification emails |
| `SMTP_USE_TLS` | Optional | `True` | Enable TLS transport for SMTP |
| `SIGNAL_NOTIFICATION_PROVIDER`| No | `in_app` / `telegram` / `discord` / `email` | Active delivery channel |

---

## 3. Deployment Runbook

### Option A: Docker Compose (Standard Production)

1. **Clone repository & prepare environment**:
   ```bash
   cp .env.example .env
   # Edit .env with production credentials:
   # nano .env
   ```

2. **Launch Services**:
   ```bash
   docker compose -f docker/docker-compose.yml up -d --build
   ```

3. **Run Database Migrations**:
   ```bash
   docker compose -f docker/docker-compose.yml exec api alembic upgrade head
   ```

4. **Verify Health**:
   ```bash
   curl -f http://localhost:8000/api/v1/health
   curl -f http://localhost:8000/api/v1/health/ready
   ```

---

### Option B: Bare Metal / Virtual Machine

1. **Prerequisites**:
   - Python 3.11+
   - PostgreSQL 14+

2. **Install Locked Dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements-lock.txt
   ```

3. **Migrate Database**:
   ```bash
   alembic upgrade head
   ```

4. **Run Production Server (4 Workers)**:
   ```bash
   uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
   ```

---

## 4. Verification Endpoints

- **Liveness Probe**: `GET /api/v1/health/live` (Returns HTTP 200 immediately)
- **Readiness Probe**: `GET /api/v1/health/ready` (Returns HTTP 200 when DB connected, 503 if unreachable)
- **System Health**: `GET /api/v1/health` (Reports app version, DB status, and AI provider status)
- **Web Dashboard**: `GET /app/` (React SPA)
- **API Documentation**: `GET /docs` (OpenAPI Swagger UI) and `GET /redoc`
- **Operator Diagnostics**: `GET /api/v1/dashboard/diagnostics`

---

## 5. Failure & Recovery Procedures

- **Database Disruption**: The readiness probe returns HTTP 503 (`not_ready`), alerting load balancers to route traffic away from the instance until connectivity is restored.
- **Worker Crash & Distributed Locks**: If a worker holding a lock on a source ingestion task crashes, the lock lease expires in 60 seconds and is safely reclaimed by subsequent runs.
- **Source Upstream Errors**: Upstream 429/5xx responses are caught and handled by `ResilientHTTPClient` with exponential backoff and rate-limit parsing. The ingestion pipeline isolates failures per source.
