# SIGNAL 📡 — Vercel Deployment Guide

This guide walks through deploying the complete full-stack **SIGNAL** platform (FastAPI Backend + React SPA Frontend) on [Vercel](https://vercel.com).

---

## Architecture on Vercel

```
                                  ┌────────────────────────┐
                                  │   Vercel Global Edge   │
                                  └───────────┬────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
               Static / SPA Routes                              /api/* & /docs
                      │                                               │
             ┌────────▼────────┐                             ┌────────▼────────┐
             │   Vite React    │                             │  FastAPI Engine │
             │  apps/web/dist  │                             │   api/index.py  │
             └─────────────────┘                             └────────┬────────┘
                                                                      │
                                                             ┌────────▼────────┐
                                                             │   PostgreSQL    │
                                                             │ (Neon/Supabase) │
                                                             └─────────────────┘
```

* **Frontend**: React + TypeScript + Tailwind CSS (compiled via Vite to `apps/web/dist`, served via Vercel Edge CDN with client-side SPA routing).
* **Backend**: FastAPI Serverless Function running via Vercel's Python runtime (`@vercel/python`) at `api/index.py`.
* **Database**: Ephemeral `/tmp/signal_dev.db` for zero-configuration preview, or cloud PostgreSQL (Neon, Supabase, Vercel Postgres) via `DATABASE_URL`.

---

## Quick Deploy (3 Steps)

### Step 1: Push Repository to GitHub
Ensure all files are committed and pushed to your GitHub repository (see [GitHub Push](#github-push) below).

### Step 2: Import into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** → **Project**.
3. Select your `signal` GitHub repository and click **Import**.
4. Vercel will automatically detect `vercel.json`:
   * **Framework Preset**: Other
   * **Build Command**: `cd apps/web && npm install && npm run build`
   * **Output Directory**: `apps/web/dist`

### Step 3: Configure Environment Variables
In the Vercel **Environment Variables** section, add:

| Variable | Recommended Value / Description | Required? |
|---|---|---|
| `ENVIRONMENT` | `production` | Recommended |
| `SECRET_KEY` | Generate a 32-character random secret key | Required |
| `JWT_SECRET_KEY` | (Optional, defaults to `SECRET_KEY`) | Optional |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@ep-host.neon.tech/neondb` (e.g. Neon, Supabase, Vercel Postgres) | Recommended for persistence |
| `ENABLE_SCHEDULER` | `false` (Serverless functions should not run persistent schedulers) | Defaulted in code |
| `CORS_ORIGINS` | `https://*.vercel.app` (Handled automatically by origin regex) | Optional |
| `GEMINI_API_KEY` | Your Google Gemini API Key | Optional |
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token for push alerts | Optional |

Click **Deploy**!

---

## Verifying Deployment

Once deployment completes:
1. **Frontend Application**:
   Navigate to `https://<your-project>.vercel.app/` — The SIGNAL dashboard terminal will load with opportunity browsing, filtering, and user onboarding.
2. **API Health Probe**:
   `GET https://<your-project>.vercel.app/api/v1/health`
   ```json
   { "status": "healthy", "service": "signal-api" }
   ```
3. **Swagger OpenAPI Documentation**:
   `GET https://<your-project>.vercel.app/docs` — Interactive API explorer.
4. **Live Ingestion Diagnostic**:
   `GET https://<your-project>.vercel.app/api/v1/dashboard/diagnostics`

---

## Triggering Scheduled Ingestion on Vercel

Because Vercel Serverless Functions freeze between requests, scheduled crawler runs can be triggered using **Vercel Cron Jobs**:

Add to `vercel.json` if automated daily crawling is desired:
```json
{
  "crons": [
    {
      "path": "/api/v1/scheduler/poll-all",
      "schedule": "0 */6 * * *"
    }
  ]
}
```
*(Requires Vercel Pro or external cron service like GitHub Actions or cron-job.org)*.
