# HelioFlow

**From First Lead to Solar Power.**

Lead qualification, quotation and project tracking for a rooftop solar installer in Nagpur
(Vidarbha). A homeowner uploads an electricity bill and AI reads it. The system scores the lead
and suggests a size. Sales sends a same-day quote with subsidy and payback, and the customer
follows the installation on a private status link.

**Live demo:** _added after deployment_

## What it does

| Who | What they can do |
|---|---|
| **Homeowner** | Check if solar fits in three steps (home, account, bill photo). Review and correct the values the AI read. See a suggested size. Open, compare and accept a quote, and download it as a PDF. Follow the installation. Everything is in English, हिन्दी and मराठी. |
| **Sales** | Work from an inbox that says what to do next on each lead, and whose move it is. Verify roof and load by visit or call. Build a quote from dated price and subsidy rules, with reasoned overrides. Record the advance, move the project stage by stage, and share or revoke the status link. |
| **Admin** | Everything sales can do, plus editing price rules, subsidy rules and settings. Overlapping rules are refused. |

Payments and WhatsApp messages are simulated and clearly labelled as such.

## How it handles the hard parts

- **When the AI is wrong or unsure.** Photos are checked for size, darkness and blur before any AI
  call. Groq reads the bill, Gemini is the fallback, and manual entry is the last resort, so a lead
  is never lost. Every value is range-checked and cross-checked (meter readings against printed
  units, multi-month bills scaled to a month). Doubtful fields are flagged, and the homeowner
  confirms every number before it is used.
- **The AI never does the maths.** Scoring, sizing, pricing, subsidy, savings and payback are plain
  Python with `Decimal`. They are tested against the brief's three sample leads.
- **Quotes don't change after they are sent.** Each quote is an immutable snapshot of the rules in
  force that day, guarded by a database trigger. A rule change only affects new quotes.
- **Privacy.** Homeowners can only ever reach their own data. Status links carry a hashed secret
  token and show only first name, project code and stages.

## Stack

| | |
|---|---|
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui, next-intl, TanStack Query |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, ReportLab (PDF) |
| AI | Groq vision (primary), Gemini Flash (fallback), manual entry (final fallback) |
| Hosting | Vercel (frontend), Render (API), Neon (database) |

## Run it

You need Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node.js 22.

```bash
docker compose up -d                                   # Postgres
cd backend && cp .env.example .env                     # fill in JWT_SECRET, SEED_DEMO_PASSWORD
uv sync && uv run alembic upgrade head && uv run python -m seed
uv run uvicorn app.main:app --reload --port 8000
cd ../frontend && cp .env.example .env.local && npm install && npm run dev
```

Full steps, environment variables, the seeded accounts and deployment are in
[docs/deployment.md](docs/deployment.md).

## Tests

- **Backend.** About 400 unit and integration tests run against a real Postgres. They cover the
  calculation engine, the upload and AI fallback chain, access control, the quote and project
  lifecycle, and the security limits.
- **Frontend.** Lint, type checks and a check that every text exists in all three languages.
- **End to end.** Playwright runs the whole journey in a browser, from the lead form to the public
  status page, plus the Hindi form at phone width.

GitHub Actions runs all three on every push.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): design, data model, AI pipeline, calculations,
  security, testing, and the numbered assumptions (A-…).
- [docs/deployment.md](docs/deployment.md): local setup, tests, deployment, and known limitations.
