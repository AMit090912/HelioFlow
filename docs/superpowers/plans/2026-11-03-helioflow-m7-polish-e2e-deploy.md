# HelioFlow M7: Polish, E2E, Deploy, Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the product for submission: the remaining polish, a full end-to-end test in CI, deployment config for Vercel + Render + Neon, `docs/deployment.md`, and the TDD.

**Architecture:** No new features. The E2E suite drives the real app (Next.js production build → FastAPI → Postgres) with Playwright. The backend runs with `AI_MODE=demo` and no keys, so only the bundled synthetic sample bill is "read", deterministically and labelled as demo. Deploy config lives in the repo (`render.yaml`, Vercel project settings documented); the user creates the accounts and pushes.

**Tech Stack:** Playwright (`@playwright/test`, already a dev dependency), GitHub Actions, Render (Python web service, uv), Neon Postgres, Vercel.

**Spec:** `docs/ARCHITECTURE.md` §15.4 (E2E), §16 (Deployment), §21 (M7 done-when: "E2E passes in CI; live URL checked from a phone; demo logins work").

## Global Constraints

- Never push, branch or open PRs; local commits only, as AMit090912, plain-English messages, no trailers.
- Never read or print `backend/.env`; secrets only as env-var names in docs and config.
- No fake AI in the real workflow: E2E uses `AI_MODE=demo` + the bundled sample bill only (labelled demo).
- Homeowner journey stays complete in en/hi/mr; `check:i18n` stays green.
- Don't invent business rules; open questions go to the user (tenant next step).

## Review Focus

1. Render cold start (free tier sleeps): the first request after idle must show the existing "waking up" state, not an error. Checked manually after deploy.
2. Cookies through the Vercel rewrite: the session cookie must be set on the Vercel origin (same-origin proxy), `Secure` in production. E2E runs against `next start` with the same rewrite.
3. A fresh Neon database: `alembic upgrade head` then `python -m seed` must work on an empty database (fixed once in M6; E2E CI runs it from empty every time).
4. Hindi on a phone: the lead form must work end to end at phone width in Hindi (the M4 done-when smoke test).
5. Upload size through the proxy: a 10 MB bill must reach FastAPI (Q-9); documented, not re-tested in E2E.

---

### Task 1: Polish carried over from review

**Files:** `backend/app/api/staff.py`, `backend/app/schemas/staff.py`, `frontend/lib/staff.ts`, inbox page, staff tests.

- [ ] Inbox Size column shows the accepted quote's size once a quote is accepted (row gains `accepted_kw: str | None`); test: accepted lead row → `accepted_kw == "1"`.
- [ ] Tenant leads' next step: **waiting on the user's answer** (call about landlord consent vs close). Not built until answered.

### Task 2: E2E suite

**Files:** `frontend/playwright.config.ts`, `frontend/e2e/*.spec.ts`, `frontend/package.json` (`e2e` script).

- [ ] `journey.spec.ts`, the §15.4 path: homeowner signs up through the lead form → uploads the sample bill → confirms values → sales signs in and sees the lead → verifies the roof → sends a quote → homeowner accepts → sales records the advance → moves one stage → public status page shows the new stage.
- [ ] `hindi-phone.spec.ts`: lead form at 390 px in Hindi through to the bill step (M4 done-when).
- [ ] Runs against `next build && next start` + `uvicorn` with `AI_MODE=demo`, a fresh database, migrations and seed.

### Task 3: E2E in CI

**Files:** `.github/workflows/ci.yml`.

- [ ] `e2e` job: Postgres service → `alembic upgrade head` → `python -m seed` → backend in the background → frontend build + start → `npx playwright install --with-deps chromium` → `npm run e2e`; upload the report on failure.

### Task 4: Deploy config

**Files:** `render.yaml`, `backend` start command, `docs/ARCHITECTURE.md` §16 (uv, not requirements.txt).

- [ ] Render blueprint: Python web service, `uv sync --frozen` build, start `alembic upgrade head && uvicorn … --port $PORT`, health check `/api/health`, env names only (`sync: false` for secrets), `TRUST_PROXY_HEADERS=true`, `ENV=production`, `COOKIE_SECURE=true`.
- [ ] Production settings checked: app refuses to start without `JWT_SECRET` in production; `FRONTEND_ORIGIN` set to the Vercel URL.

### Task 5: `docs/deployment.md` and README

- [ ] Local setup (Docker Postgres, uv, npm, seed, dev servers, demo mode).
- [ ] Neon → Render → Vercel steps in order, env-var tables (names only), seeding, `DEMO_LOGINS`, AI keys and free-tier rate limits, cold starts, storage limit, known limitations.

### Task 6: TDD

- [ ] Word document, GitHub URL and live URL at the top (placeholders until the user deploys), built from ARCHITECTURE.md: problem, users, architecture, data model, AI, calculations with the sample-lead numbers, security, testing (actual counts), assumptions, limitations, what's next.

### Task 7: Review and hand-off

- [ ] Fresh reviewer over the M7 diff; fix pass; full test run (backend, frontend checks, E2E) with real output.
- [ ] User pushes to GitHub and connects Render/Vercel/Neon following deployment.md; then check the live URL from a phone and fill the URLs into the TDD.
