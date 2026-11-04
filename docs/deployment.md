# HelioFlow: deployment and demo guide

**Live app:** https://helio-flow-nine.vercel.app
**Source:** https://github.com/AMit090912/HelioFlow

This guide has three parts:

1. [Demo login details](#1-demo-login-details): how to sign in on the live site as a
   homeowner, sales or admin.
2. [Run it locally](#2-run-it-locally-step-by-step), step by step.
3. [How it is deployed](#3-how-it-is-deployed), and the
   [environment variables](#4-environment-variables) it needs.

Environment variables are listed by name only. Real values (keys, secrets, database URLs) never
go in the repository.

---

## 1. Demo login details

Open https://helio-flow-nine.vercel.app and choose **Sign in** (top right). Everyone uses the same
sign-in page. The app sends each role to its own area after sign-in.

**Password for all seeded accounts on the live site:** in the submitted copy of this file (see the note below).

> The live password is written only in the copy of this file submitted in the ZIP. It is not
> published on GitHub, because anyone with it can sign in as admin and change price rules.

| Role | Sign in with | What you'll see |
|---|---|---|
| **Sales** | `sales@helioflow.example` | The leads inbox. Each lead says what to do next and whose move it is. Verify the roof, build and send a quote, record the advance, move the installation stage, share the status link. |
| **Admin** | `admin@helioflow.example` | Everything sales sees, plus **Rules**: price rules, subsidy rules and settings, which only an admin can edit. |
| **Homeowner** (Prashant, owner, ₹3,200 bill) | `prashant@helioflow.example` or mobile `9000000001` | The homeowner dashboard for a lead from the brief. |
| **Homeowner** (Rohit, tenant, ₹1,900 bill) | `rohit@helioflow.example` or mobile `9000000002` | A tenant lead. Tenants aren't quoted under the current rules, so sales calls to talk through options with them and their landlord. |
| **Homeowner** (Ayesha, owner, ₹650 bill) | `ayesha@helioflow.example` or mobile `9000000003` | A small bill: sales calls first instead of booking a survey. |

**The quickest way to try the whole journey** is as a new homeowner, then as sales:

1. Signed out, choose **Get solar** on the home page. Fill in the home details and create an
   account (any email or a 10-digit mobile number, and a password of your own).
2. Upload a bill. No bill to hand? Use one from [`samples/bills/`](../samples/bills) in the
   repository; its README lists the values the app should read. Check the values and confirm.
3. Sign out and sign in as **sales**. Your new lead is at the top of the inbox. Verify the roof
   and load, then send a quote.
4. Sign back in as the homeowner. Open the quote, download the PDF and accept it.
5. As sales, record the advance (simulated payment), move the installation stage and copy the
   status link. Open the link in a private window: it works without signing in.

Switch language at any time from the language menu: English, हिन्दी, मराठी.

**Before you start:**
- The API runs on Render's free tier and sleeps after about 15 minutes idle. The first request
  then takes 30 to 60 seconds, and the app shows "Waking up the server…" meanwhile. That's
  expected, not an error.
- Payments and WhatsApp messages are simulated and labelled as such. No money moves and no
  message is sent.

---

## 2. Run it locally, step by step

### What you need

- Docker (for Postgres)
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 22

### Step 1: start the database

From the repository root:

```bash
docker compose up -d
```

This starts Postgres 16 on port **5433**, with a `helio` database for the app and an empty
`helio_test` database for the tests.

### Step 2: configure the API

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and fill in at least these:

| Name | What to put for local use |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://helio:helio@localhost:5433/helio` |
| `TEST_DATABASE_URL` | `postgresql+psycopg://helio:helio@localhost:5433/helio_test` |
| `JWT_SECRET` | any long random string |
| `FRONTEND_ORIGIN` | `http://localhost:3000` |
| `COOKIE_SECURE` | `false` (local HTTP) |
| `AI_MODE` | `demo` without AI keys, or `live` with them (see below) |
| `SEED_DEMO_PASSWORD` | **a password you choose.** Every seeded account gets it, so it's the password you'll sign in with locally. |
| `DEMO_LOGINS` | `true` to get one-click sign-in buttons for each role on the sign-in page (optional) |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | optional; without them, bills go to manual entry |

### Step 3: install, migrate, seed and start the API

```bash
uv sync                          # install Python dependencies
uv run alembic upgrade head      # create the tables
uv run python -m seed            # sales, admin, the three brief leads, price and subsidy rules
uv run uvicorn app.main:app --reload --port 8000
```

The seed is safe to run again: it only adds what's missing. Check http://localhost:8000/api/health
returns `{"status":"ok"}`.

### Step 4: start the frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env.local       # already contains BACKEND_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000. Sign in with the accounts in [section 1](#1-demo-login-details),
using the `SEED_DEMO_PASSWORD` you chose in step 2.

### Reading bills: AI modes

- **`AI_MODE=live`**: reads bills with Groq. If Groq fails, Gemini is tried, then the homeowner
  types the values in. Needs `GROQ_API_KEY` and/or `GEMINI_API_KEY`.
- **`AI_MODE=demo`**: recognises only the bundled synthetic sample
  (`samples/bills/sample-bill-demo.jpg`) and labels its reading as a demo. Any other bill goes to
  the live chain, or to manual entry when no keys are set. Demo mode never pretends to read a real
  bill.

### Run the tests

```bash
# Backend: about 400 unit and integration tests against the helio_test database
cd backend
uv run pytest -q
uv run ruff check .

# Frontend: lint, types, the same text in all three languages, production build
cd frontend
npm run lint
npm run typecheck
npm run check:i18n
npm run build
```

**End-to-end tests** drive a real browser through the whole journey:

1. A homeowner signs up through the lead form, uploads the sample bill and confirms it.
2. Sales verifies the roof and sends a quote, then a revised one.
3. The homeowner opens the old quote link, lands on the newest one, downloads the PDF and
   accepts it.
4. Sales records the advance and moves a stage.
5. The public status page shows the new stage.

A second test runs the Hindi lead form at phone width.

They use their own database (`helio_e2e`) and start their own API (port 8100, `AI_MODE=demo`, no
AI keys) and production frontend build (port 3100).

```bash
docker exec isocod-db-1 psql -U helio -d helio -c "CREATE DATABASE helio_e2e;"   # once
cd backend
DATABASE_URL=postgresql+psycopg://helio:helio@localhost:5433/helio_e2e uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://helio:helio@localhost:5433/helio_e2e SEED_DEMO_PASSWORD=<your password> uv run python -m seed
cd ../frontend
npx playwright install chromium   # once
SEED_DEMO_PASSWORD=<your password> npm run e2e
```

GitHub Actions runs the backend, frontend and end-to-end jobs on every push
(`.github/workflows/ci.yml`).

---

## 3. How it is deployed

All three services run on free tiers.

```
Browser ──► Next.js on Vercel ──/api/* rewrite──► FastAPI on Render ──► Postgres on Neon
                                                        └──► Groq → Gemini (bill reading only)
```

| Part | Service | Notes |
|---|---|---|
| Frontend | **Vercel** (Hobby) | Next.js. Every `/api/*` request is forwarded to the API, so the browser only talks to one domain. The session cookie stays first-party, and no CORS is needed. |
| API | **Render** (free web service, Singapore) | FastAPI, defined in `render.yaml`. Database migrations run on every start. |
| Database | **Neon** (free Postgres, Singapore) | Uploaded bills are stored here too (`bill_files`), and only their owner and staff can open them. |
| AI | **Groq**, falling back to **Gemini** | Called only by the API; the keys never reach the browser. |

### Deploying it yourself

Do these in order: each step needs a value from the one before.

**1. Neon (database)**

1. Create a project in the region closest to India (AWS Singapore).
2. Copy the connection string (`postgresql://…?sslmode=require`). Paste it as it is: the API
   converts it for its database driver.

**2. Render (API)**

1. In Render, choose **New → Blueprint** and pick the GitHub repository. Render reads
   `render.yaml` and creates the `helioflow-api` web service.
2. Fill in the values the blueprint leaves to you: `DATABASE_URL`, `FRONTEND_ORIGIN` (use a
   placeholder until step 3), `GROQ_API_KEY`, `GEMINI_API_KEY` and, optionally, `DEMO_LOGINS`.
3. The blueprint sets the rest:
   - `ENV=production`, `AI_MODE=live`, `COOKIE_SECURE=true`, `TRUST_PROXY_HEADERS=true`.
   - Python 3.12.
   - A generated `JWT_SECRET`. In production the API refuses to start with a secret shorter
     than 32 characters.
4. Deploy. Check `https://<render-url>/api/health` returns `{"status":"ok"}`.
5. **Seed the database once, from your own machine.** Render's free tier has no shell:

   ```bash
   cd backend
   DATABASE_URL='<neon connection string>' SEED_DEMO_PASSWORD='<a new strong password>' uv run python -m seed
   ```

   This password becomes the live password for every seeded account. Don't reuse your local
   one.

**3. Vercel (frontend)**

1. **Add New → Project**, pick the repository and set **Root Directory** to `frontend`.
2. Add one environment variable, `BACKEND_URL`: the Render URL, with no trailing slash. It is
   read at build time, so redeploy after changing it.
3. Deploy. Then put the Vercel URL into Render's `FRONTEND_ORIGIN` and let Render redeploy.

After that, every push to `main` redeploys both Vercel and Render automatically.

---

## 4. Environment variables

Names only. Values are set in each host's dashboard, or in local files that git ignores.

**API** (Render, or `backend/.env` locally)

| Name | Required | What it does |
|---|---|---|
| `ENV` | yes | `development`, `test` or `production`. Production hides the API docs and test routes, and enforces the `JWT_SECRET` length. |
| `DATABASE_URL` | yes | Postgres connection string. `postgresql://` and `postgres://` are both accepted. |
| `TEST_DATABASE_URL` | tests only | The database the backend tests use. |
| `JWT_SECRET` | yes | Signs session cookies. At least 32 characters in production. |
| `JWT_TTL_HOURS` | no | How long a sign-in lasts. Default 8. |
| `FRONTEND_ORIGIN` | yes | The frontend's URL. |
| `COOKIE_SECURE` | yes | `true` on HTTPS, `false` for local HTTP. |
| `TRUST_PROXY_HEADERS` | production | `true` behind Vercel and Render, so rate limits see the visitor's IP. |
| `AI_MODE` | yes | `live` in production. `demo` for the labelled sample-bill demo. `test` only in automated tests. |
| `GROQ_API_KEY` | for AI | Groq, the primary bill reader. |
| `GEMINI_API_KEY` | for AI | Gemini, the fallback reader. Without both keys, every bill goes to manual entry. |
| `GROQ_VISION_MODEL`, `GROQ_TEXT_MODEL`, `GEMINI_MODEL` | no | Leave blank for the defaults. |
| `AI_TIMEOUT_SECONDS` | no | Time limit per AI call. Default 20. |
| `MAX_UPLOAD_MB` | no | Largest bill upload. Default 10. |
| `DEMO_LOGINS` | no | `true` shows one-click sign-in for each role. Off unless set. |
| `SEED_DEMO_PASSWORD` | seeding only | The password the seed gives every seeded account. Needed wherever `python -m seed` runs, not on Render. |

**Frontend** (Vercel, or `frontend/.env.local` locally)

| Name | Required | What it does |
|---|---|---|
| `BACKEND_URL` | yes | The API's URL. Used on the server only, at build time. |

---

## 5. Known limitations of the free-tier deployment

- **Cold starts.** The free API sleeps after about 15 minutes idle, and the next request takes
  30 to 60 seconds. A paid instance removes this.
- **AI rate limits.** The free Groq and Gemini tiers cap requests per minute and per day. When
  both are used up, the homeowner types the values in instead, and nothing is lost.
- **Bill storage.** Bills are stored in Postgres, and Neon's free storage is about 0.5 GB.
  Production would move them to private object storage with signed links (A-12).
- **Rate limits live in memory.** Sign-in, sign-up and upload limits are kept per server process.
  That's fine for one Render instance; several instances would need a shared store such as Redis.
- **Proxy trust.** Per-visitor limits use the first `X-Forwarded-For` address. Vercel sets it,
  but someone calling the Render URL directly can fake it. Backstops limit the damage:
  - an account stops accepting sign-ins for a while after 20 failed attempts in 15 minutes;
  - sign-ups are capped at 200 an hour in total.

  A production setup would accept API traffic only from the frontend.
- **Signing out is per browser.** Signing out deletes the session cookie. A copy of the cookie
  taken earlier stays valid until it expires (8 hours).
- **A ₹0 quote can't be converted.** If a price rule is set below the subsidy, the cost after
  subsidy can be ₹0. Such a quote can be accepted but not converted, because the advance must be
  at least ₹1.
- **Upload limits per homeowner.** 10 accepted bills and 30 attempts an hour.
- **Simulated services.** WhatsApp messages are stored and shown as "Simulated, not sent". The
  advance gets a `SIMULATED-` reference.
- **Screens don't update live.** When one side acts (sales sends a quote, the homeowner accepts, a
  stage moves), the other side's open screen doesn't change until the page is refreshed. Only the
  bill-reading progress updates by itself, and the homeowner's dashboard reloads when its tab is
  opened again. Live updates (WebSockets or server-sent events) are planned for a future version.
- **No email or in-app notifications.** The homeowner gets no email when a quote is sent or
  updated, and sales gets no alert for a new lead or an accepted quote; they see it by opening the
  inbox. Planned for a future version.
- **Hosting logs.** The app removes status-link tokens from its own logs. Render and Vercel keep
  their own request logs, which the app can't change.
