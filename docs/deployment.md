# HelioFlow: running and deploying

This guide covers running HelioFlow on your own machine, running the tests, and deploying it to
Vercel (frontend), Render (API) and Neon (Postgres). Environment variables are listed by name
only. Real values never go in the repository.

## What runs where

```
Browser ──► Next.js on Vercel ──/api/* rewrite──► FastAPI on Render ──► Postgres on Neon
                                                        └──► Groq → Gemini (bill reading only)
```

- The browser only ever talks to the Next.js app. `/api/*` is proxied to FastAPI, so the session
  cookie is first-party on the frontend's domain and no CORS is needed in normal use.
- AI keys live only on the API server. The frontend holds one setting, `BACKEND_URL`, which is
  server-side only.
- Uploaded bills are stored in Postgres (`bill_files`) and served only to their owner and staff.

## 1. Run it locally

**You need:** Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node.js 22.

```bash
# 1. Database (Postgres 16 on port 5433, plus an empty helio_test database for the tests)
docker compose up -d

# 2. API
cd backend
cp .env.example .env          # then fill in the values below
uv sync
uv run alembic upgrade head
uv run python -m seed         # staff, admin, the three brief leads, price and subsidy rules
uv run uvicorn app.main:app --reload --port 8000

# 3. Frontend (second terminal)
cd frontend
cp .env.example .env.local    # BACKEND_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:3000
```

In `backend/.env`, set at least:

| Name | Value for local use |
|---|---|
| `JWT_SECRET` | any long random string |
| `SEED_DEMO_PASSWORD` | the password the seeded staff, admin and demo homeowners get |
| `COOKIE_SECURE` | `false` (local HTTP) |
| `AI_MODE` | `live` with keys, or `demo` (see below) |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | optional locally; without them bills go to manual entry |

**Seeded accounts** (all use `SEED_DEMO_PASSWORD`):

| Role | Sign in with |
|---|---|
| Sales | `sales@helioflow.example` |
| Admin (edits price and subsidy rules) | `admin@helioflow.example` |
| Homeowners from the brief | `prashant@`, `rohit@`, `ayesha@helioflow.example` |

**Test bills.** `samples/bills/` holds three synthetic bills and the values each should read
(see its README). Upload one at the bill step.

**AI modes.** `AI_MODE=live` reads bills with Groq, falls back to Gemini, then to manual entry.
`AI_MODE=demo` recognises only the bundled synthetic sample bill
(`backend/app/services/ai/samples/sample-bill.jpg`) and labels its reading as a demo. Any other
bill still goes to the live chain, or to manual entry when no keys are set. Demo mode never
pretends to read a real bill.

## 2. Run the tests

```bash
# Backend: unit + integration tests against the helio_test database
cd backend && uv run pytest -q && uv run ruff check .

# Frontend: lint, types, translation-key parity (en/hi/mr), production build
cd frontend && npm run lint && npm run typecheck && npm run check:i18n && npm run build
```

**End-to-end tests** run the whole journey in a real browser against a production build:

1. A homeowner signs up through the lead form, uploads the sample bill and confirms it.
2. Sales verifies the roof and sends a quote.
3. The homeowner downloads the PDF and accepts the quote.
4. Sales records the advance and moves a stage.
5. The public status page shows the new stage.

A second test runs the Hindi lead form at phone width.

They use their own database, `helio_e2e`, and start the API (port 8100) and the frontend
(port 3100) themselves. The API runs with `AI_MODE=demo` and empty AI keys, so nothing calls a
live AI.

```bash
docker exec isocod-db-1 psql -U helio -d helio -c "CREATE DATABASE helio_e2e;"   # once
cd backend
DATABASE_URL=postgresql+psycopg://helio:helio@localhost:5433/helio_e2e uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://helio:helio@localhost:5433/helio_e2e SEED_DEMO_PASSWORD=<pw> uv run python -m seed
cd ../frontend
npx playwright install chromium   # once
SEED_DEMO_PASSWORD=<pw> npm run e2e
```

GitHub Actions runs all three jobs on every push: backend, frontend, and the end-to-end tests on a
fresh database (`.github/workflows/ci.yml`).

## 3. Deploy

Do the steps in this order: each one needs a value from the one before.

### 3.1 Neon (database)

1. Create a project. Pick the region closest to India, e.g. AWS Singapore.
2. Copy the connection string (`postgresql://…?sslmode=require`). You can paste it as it is: the
   API maps it to the psycopg 3 driver.

### 3.2 Render (API)

1. Push the repository to GitHub. In Render, choose **New → Blueprint** and pick the repository.
   Render reads `render.yaml` and creates the `helioflow-api` web service.
2. Fill in the values marked "sync: false":

| Name | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string |
| `FRONTEND_ORIGIN` | the Vercel URL (come back after 3.3; use a placeholder for now) |
| `GROQ_API_KEY` | from console.groq.com |
| `GEMINI_API_KEY` | from Google AI Studio |
| `DEMO_LOGINS` | `true` to show one-click sign-in as each role (for reviewers), else leave blank |

   The blueprint sets everything else itself:
   - `ENV=production`, `AI_MODE=live`, `COOKIE_SECURE=true`, `TRUST_PROXY_HEADERS=true`.
   - Python 3.12.
   - A generated `JWT_SECRET`. In production the app refuses to start with a secret shorter
     than 32 characters.
3. Deploy. Each start runs `alembic upgrade head`, which is safe to repeat, and then the server.
   Check `https://<render-url>/api/health` returns `{"status":"ok"}`.
4. **Seed once, from your machine.** Render's free tier has no shell. The seed is idempotent, so
   running it twice does nothing new.

   ```bash
   cd backend
   DATABASE_URL='<neon connection string>' SEED_DEMO_PASSWORD='<choose a password>' uv run python -m seed
   ```

   Choose a new, strong password here, not the one you use locally: anyone who knows it can sign in
   as sales or admin on the live site.

### 3.3 Vercel (frontend)

1. **Add New → Project**, pick the repository, set **Root Directory** to `frontend`. Vercel
   detects Next.js.
2. Add one environment variable: `BACKEND_URL` = the Render URL (`https://helioflow-api.onrender.com`,
   no trailing slash). It is read at build time by the `/api/*` rewrite, so redeploy after
   changing it.
3. Deploy, then put the Vercel URL into Render's `FRONTEND_ORIGIN` and let Render redeploy.

### 3.4 Check the live site

Open the Vercel URL on a phone and check, in order:

- [ ] The home page loads. The first request after the API has been idle shows "Waking up the
      server…" for up to a minute; that's Render's free tier, not an error.
- [ ] The language switch works: English, हिन्दी, मराठी.
- [ ] The lead form completes. A bill photo uploads and is read, or goes to manual entry if the
      AI is rate-limited.
- [ ] Sign in as sales: the inbox lists the three brief leads. Verify a roof, send a quote,
      open the PDF.
- [ ] As the homeowner, accept the quote. As sales, record the advance and open the status link
      signed out.
- [ ] If `DEMO_LOGINS=true`, the sign-in page offers one-click sign-in for each role.

## 4. Environment variables

**API (Render or `backend/.env`)**

| Name | Required | Notes |
|---|---|---|
| `ENV` | yes | `development`, `test` or `production`. Production hides `/api/dev/*` and enforces the `JWT_SECRET` length |
| `DATABASE_URL` | yes | Postgres URL; `postgresql://` and `postgres://` are accepted |
| `JWT_SECRET` | yes | At least 32 characters in production |
| `JWT_TTL_HOURS` | no | Session length, default 8 |
| `FRONTEND_ORIGIN` | yes | The frontend's URL (CORS allow-list) |
| `COOKIE_SECURE` | yes | `true` on HTTPS |
| `TRUST_PROXY_HEADERS` | prod | `true` behind Vercel and Render, so rate limits see the visitor's IP |
| `AI_MODE` | yes | `live` in production. `demo` for the labelled sample-bill demo; `test` only in automated tests |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | for AI | Without both, every bill goes to manual entry |
| `GROQ_VISION_MODEL`, `GROQ_TEXT_MODEL`, `GEMINI_MODEL` | no | Leave blank for the defaults (`qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, `gemini-3.5-flash`) |
| `AI_TIMEOUT_SECONDS` | no | Per provider call, default 20 |
| `MAX_UPLOAD_MB` | no | Default 10 |
| `DEMO_LOGINS` | no | `true` shows one-click role sign-in. Off unless set |
| `SEED_DEMO_PASSWORD` | seed only | Needed wherever `python -m seed` runs; not needed on Render |

**Frontend (Vercel or `frontend/.env.local`)**

| Name | Notes |
|---|---|
| `BACKEND_URL` | The API's URL. Server-side only, used by the `/api/*` rewrite at build time |

## 5. Known limitations of the free-tier deployment

- **Cold starts.** Render's free API sleeps after about 15 minutes idle. The first request then
  takes 30–60 s, and the app shows a "waking up" state meanwhile. A paid instance removes this.
- **AI rate limits.** The free Groq and Gemini tiers allow a limited number of requests per
  minute and per day. When both are exhausted, the homeowner is asked to type the values
  instead, and nothing is lost. Heavy testing in one day can hit the daily limit.
- **Bill storage.** Bills are stored in Postgres, and Neon's free storage is small (about
  0.5 GB). Production would move `bill_files` to private object storage with signed URLs (A-12).
- **Upload size through Vercel.** The app accepts bills up to 10 MB, and photos are compressed in
  the browser first. Check large PDFs once after deploying, because Vercel may cap proxied
  request bodies (Q-9).
- **Rate limits are per process.** Sign-in, sign-up and status-link limits are kept in memory.
  That's fine for one Render instance; several instances would need a shared store, e.g. Redis.
- **Proxy trust.** With `TRUST_PROXY_HEADERS=true`, per-client limits use the first
  `X-Forwarded-For` hop. Vercel sets that header, but a caller who goes to the Render URL directly
  can set their own. Backstops that ignore the IP limit what that buys an attacker:
  - after 20 failed sign-ins in 15 minutes, an account stops accepting attempts for a while;
  - sign-ups are capped at 200 an hour in total.

  A production setup would accept API traffic only from the frontend, through a private network
  or a shared secret.
- **Sign-out is per browser.** Sessions are signed cookies (8 hours). Signing out deletes the
  cookie, but a copy taken before sign-out stays valid until it expires. Revoking sessions on the
  server would need a session table or a token version per user.
- **A quote whose cost after subsidy is ₹0** (only possible with an unusually low price rule)
  can be accepted but not converted, because an advance must be at least ₹1 and no more than
  that cost. Don't set price rules below the subsidy.
- **Bill upload limits.** A homeowner can upload 10 accepted bills and make 30 attempts an hour.
  Past that they are asked to try again in an hour.
- **Messages and payments are simulated.** WhatsApp messages are stored and shown as
  "Simulated, not sent". The advance gets a `SIMULATED-` reference, and no money moves.
- **Hosting logs.** Status-link tokens are redacted from the app's own logs (`/s/****`). Render
  and Vercel keep their own request logs, which the app can't redact.
