# HelioFlow M1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runnable monorepo with FastAPI and Next.js. It includes the full Postgres schema and constraints, cookie-based auth with RBAC, en/hi/mr routing with a language switcher, branded shells, idempotent seed data and CI. Every later milestone builds on it.

**Architecture:** FastAPI (sync SQLAlchemy 2 + psycopg 3) owns the database and all rules. Next.js App Router proxies `/api/*` to FastAPI, so the httpOnly session cookie is same-origin. Postgres runs locally in Docker Compose, with a separate `helio_test` database for tests.

**Tech Stack:** Python 3.12 (uv), FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 + pydantic-settings, pwdlib[argon2], PyJWT, slowapi, pytest + httpx · Node 22, Next.js (latest stable from `create-next-app`), TypeScript, Tailwind, shadcn/ui, next-intl, TanStack Query · Postgres 16 · GitHub Actions.

**Spec:** `docs/ARCHITECTURE.md` (Revision 3). Section numbers below (§n) refer to it.

## Global Constraints

- **Claude never runs `git commit`, `git push`, `git init`, branch or config commands.** Every "Commit" step means: *list the changed files and suggest a commit message (no trailers) for Amit*.
- No secrets in the repo. `.env` files are git-ignored. Only `*.env.example` files with **names** are committed.
- Python 3.12 via `uv`. Money and kW are `Decimal`/`numeric`, never float (§1).
- Every API error body is `{"error": {"code": "UPPER_SNAKE", "message": "English fallback"}}`. The frontend translates by `code` (§2 Languages).
- Session cookie `hf_session`: httpOnly, SameSite=Lax, Secure when `COOKIE_SECURE=true`, 8 h (§4).
- Every unsafe method (POST/PUT/PATCH/DELETE) requires header `X-HF-CSRF: 1`, otherwise 403 `CSRF_HEADER_MISSING` (§4).
- Locales `en`, `hi`, `mr`, always prefixed in the URL. Default `en` (§2).
- Palette is taken from the client-supplied logo: brand teal and brand gold (Task 6), warm-grey neutrals, amber only for attention, red only for errors (§20, as amended in Task 9).
- Local Postgres: `postgresql+psycopg://helio:helio@localhost:5433/helio` (dev) and `/helio_test` (tests). These are local-only credentials, not secrets.

## Review Focus

1. **Email in different case or with spaces** (`" Prashant@Example.com "`): sign-up and login treat it as the same account. Test in Task 4.
2. **Phone in Indian formats** (`+91 98765 43210`, `098765-43210`): normalised to `9876543210` for both sign-up and login. Test in Task 4.
3. **Expired or tampered session cookie:** `/api/auth/me` returns 401 `NOT_AUTHENTICATED`, and the frontend sends the user to sign-in once, with no redirect loop. Test in Task 4 (API) and Task 8 (manual).
4. **Unknown locale in the URL** (`/fr/sign-in`): redirects to `/en/sign-in`, never a 500. Checked in Task 7.
5. **Sign-up payload that tries to set `"role": "admin"`:** the account is still created as `homeowner`. Test in Task 4.

---

### Task 1: Repository scaffold, local Postgres, backend skeleton with health check

**Files:**
- Create: `.gitignore`, `README.md` (short: what it is and links to docs), `docker-compose.yml`, `docker/initdb/01-test-db.sql`
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/errors.py`, `backend/app/api/__init__.py`, `backend/app/api/health.py`
- Test: `backend/tests/__init__.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.main.create_app() -> FastAPI` and `app.main.app`. All routers are mounted under the prefix `/api`.
- Produces: `app.core.config.Settings` (pydantic-settings, reads `backend/.env`) with fields `env: Literal["development","test","production"]="development"`, `database_url: str`, `jwt_secret: str`, `jwt_ttl_hours: int = 8`, `frontend_origin: str = "http://localhost:3000"`, `cookie_secure: bool = True`, `ai_mode: Literal["live","demo","test"] = "live"`, `max_upload_mb: int = 10`, `seed_demo_password: str | None = None`, plus `get_settings() -> Settings` (lru_cached).
- Produces: `app.core.errors.ApiError(status: int, code: str, message: str)`, an exception with a handler registered in `create_app` that renders the Global Constraints error body. A handler also converts `RequestValidationError` → 422 `VALIDATION_ERROR` with `details` (field paths only, no input values echoed).

- [ ] **Step 1:** `.gitignore` covers `.env`, `.env.*` except `*.env.example`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `.pytest_cache/`, `coverage/`, `*.local.json` under `.claude/`, `playwright-report/`, `test-results/`.
- [ ] **Step 2:** `docker-compose.yml`: service `db`, image `postgres:16-alpine`, env `POSTGRES_USER=helio`, `POSTGRES_PASSWORD=helio`, `POSTGRES_DB=helio`, port `5433:5432`, named volume, healthcheck `pg_isready`. Mount `docker/initdb` to `/docker-entrypoint-initdb.d`, where `01-test-db.sql` does `CREATE DATABASE helio_test OWNER helio;`.
- [ ] **Step 3:** In `backend/`, run `uv init --python 3.12 --no-workspace` style setup (or write `pyproject.toml` by hand) with deps `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `psycopg[binary]>=3.2`, `alembic`, `pydantic>=2`, `pydantic-settings`, `email-validator`, `pwdlib[argon2]`, `pyjwt`, `slowapi`, `python-multipart`. Dev group: `pytest`, `pytest-cov`, `httpx`, `ruff`. Run `uv sync`.
- [ ] **Step 4: Write the failing test** `tests/test_health.py::test_health_ok`: `TestClient(create_app()).get("/api/health")` → 200, JSON `{"status": "ok"}`. Plus `test_unknown_route_uses_error_shape`: `GET /api/nope` → 404 with `body["error"]["code"] == "NOT_FOUND"`.
- [ ] **Step 5:** Run `uv run pytest tests/test_health.py -v`. Expected: FAIL (module missing).
- [ ] **Step 6:** Implement `config.py`, `errors.py` (handlers for `ApiError`, Starlette `HTTPException` → code from status: 404 `NOT_FOUND`, 405 `METHOD_NOT_ALLOWED`, and validation), `health.py` and `main.py`.
- [ ] **Step 7:** Run the test again. Expected: PASS.
- [ ] **Step 8:** Run `docker compose up -d db`, then `docker compose ps`. Expected: `db` is healthy.
- [ ] **Step 9: Commit (Amit).** Suggested message: `chore: scaffold monorepo, docker postgres and FastAPI health endpoint`

---

### Task 2: Database models, baseline migration, constraint guarantees

**Files:**
- Create: `backend/app/core/db.py`, `backend/app/models/__init__.py`, `base.py`, `enums.py`, `user.py`, `lead.py`, `bill.py`, `rules.py`, `quote.py`, `project.py`, `notification.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_baseline.py`
- Test: `backend/tests/conftest.py`, `backend/tests/integration/test_constraints.py`

**Interfaces:**
- Produces: `app.core.db.engine`, `SessionLocal`, `get_db() -> Iterator[Session]`.
- Produces ORM classes `User, Lead, BillFile, BillReading, PriceRule, SubsidyRule, Setting, Quote, Project, ProjectEvent, Notification`. Columns exactly as in spec §3.1–§3.11, with these decisions:
  - PK `id: UUID` default `uuid.uuid4`; `created_at timestamptz` server default `now()`.
  - Enums are native Postgres enums with lower-case values from spec. Names: `user_role`, `locale`, `ownership`, `property_type`, `roof_type`, `lead_status`, `lead_score`, `next_action`, `roof_verified_via`, `bill_kind`, `reading_status`, `reading_source`, `quote_status`, `project_stage`, `notification_type`, `notification_channel`.
  - `lead_status` values: `draft, bill_processing, bill_review, qualified, survey_pending, call_pending, surveyed, quoted, accepted, converted, closed_lost`.
  - `project_stage` values: `advance_received, installation_scheduled, installation_completed, net_metering_completed, subsidy_applied, subsidy_credited`.
  - Extra column `leads.seed_note text null`, so synthetic seed values are labelled (§8.1). It is added to the spec in Task 9.
  - `bill_files.content` and `preview_png` use `deferred()`.
  - `bill_readings.bill_file_id` is **UNIQUE**.
  - `price_rules` and `subsidy_rules` get `ExcludeConstraint(..., using="gist")` with expressions `numrange(min_kw, max_kw, '[]')` / `daterange(effective_from, coalesce(effective_to, 'infinity'::date), '[]')` as in §3.5/§3.6, plus CHECKs `effective_to IS NULL OR effective_to >= effective_from`, `min_kw <= max_kw`, `price_per_kw > 0`, `cap_amount >= 0`.
  - `users`: CHECK `email IS NOT NULL OR phone IS NOT NULL`; `email` type `CITEXT` (via `sqlalchemy.dialects.postgresql.CITEXT`).
  - `quotes`: partial unique index `uq_quotes_one_open_per_lead ON quotes(lead_id) WHERE status = 'sent'`.
- Migration `0001_baseline` begins with `CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS btree_gist;`, creates everything (autogenerate, then reviewed by hand), and ends with the `quotes_guard` trigger (below). `downgrade()` drops everything in reverse order.
- Produces in `tests/conftest.py`: fixture `db_session` (each test in a transaction rolled back at the end), fixture `client` (TestClient with `get_db` overridden to `db_session`), session-scoped setup that recreates the `public` schema on `TEST_DATABASE_URL` and runs `alembic upgrade head`.

`quotes_guard` (BEFORE UPDATE, PL/pgSQL) is the one algorithm the tests don't fully determine:
```
IF NEW.number, lead_id, priced_on, snapshot, calc_version, created_by, sent_at IS DISTINCT FROM OLD → RAISE 'QUOTE_IMMUTABLE'
IF OLD.selected_kw, accepted_at, accepted_by, superseded_at, superseded_by_quote_id IS NOT NULL
   AND NEW value IS DISTINCT FROM OLD value → RAISE 'QUOTE_FIELD_ALREADY_SET'
IF NEW.status IS DISTINCT FROM OLD.status:
   allowed only (sent→accepted) or (sent→superseded); else RAISE 'QUOTE_INVALID_TRANSITION'
   sent→accepted requires NEW.accepted_at, NEW.selected_kw NOT NULL
   sent→superseded requires NEW.superseded_at NOT NULL
```
(`selected_kw ∈ snapshot options` is checked in the service layer in M5, not in the trigger.)

- [ ] **Step 1: Write the failing tests** in `test_constraints.py`, each inserting rows directly with the ORM:
  - `test_extensions_present`: `SELECT extname FROM pg_extension` includes `citext` and `btree_gist`.
  - `test_email_unique_case_insensitive`: insert `A@x.com`, then `a@x.com` → `IntegrityError`.
  - `test_user_needs_email_or_phone`: both null → `IntegrityError`.
  - `test_bill_reading_unique_per_file`: two readings with the same `bill_file_id` → `IntegrityError`.
  - `test_price_rule_overlap_rejected`: 1–10 kW from 2026-01-01 open-ended, then 3–5 kW from 2026-06-01 → `IntegrityError`; 1–10 kW from 2025-01-01 to 2025-12-31 → OK (adjacent, not overlapping).
  - `test_subsidy_rule_overlap_rejected`: same scheme and segment, overlapping dates → error; different `scheme_code` → OK.
  - `test_quote_snapshot_immutable`: insert quote with status `sent`; update `snapshot` → `DBAPIError` containing `QUOTE_IMMUTABLE`.
  - `test_quote_valid_and_invalid_transitions`: sent→accepted with `accepted_at`, `selected_kw` → OK; accepted→sent → `QUOTE_INVALID_TRANSITION`; changing `accepted_at` again → `QUOTE_FIELD_ALREADY_SET`.
  - `test_one_open_quote_per_lead`: two `sent` quotes for one lead → `IntegrityError`.
- [ ] **Step 2:** Run `uv run pytest tests/integration/test_constraints.py -v`. Expected: FAIL (no models or migration).
- [ ] **Step 3:** Implement `db.py`, the models and enums.
- [ ] **Step 4:** Configure Alembic (`env.py` reads `get_settings().database_url`, `target_metadata = Base.metadata`, `compare_type=True`). Run `uv run alembic revision --autogenerate -m baseline`, rename to `0001_baseline.py`, add the extensions at the top and the trigger SQL at the bottom, and check by hand that the exclusion constraints and partial index are present.
- [ ] **Step 5:** Run `uv run alembic upgrade head` against dev, then `uv run alembic downgrade base` and `upgrade head` again. Expected: all three succeed.
- [ ] **Step 6:** Run the tests. Expected: all PASS.
- [ ] **Step 7: Commit (Amit).** Suggested message: `feat(db): add full schema, rule overlap constraints and quote immutability trigger`

---

### Task 3: Password hashing and session tokens

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/core/common_passwords.txt` (about 200 most common passwords, lower-case)
- Test: `backend/tests/unit/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(plain: str) -> str` (argon2id via pwdlib)
  - `verify_password(plain: str, hashed: str) -> bool`
  - `is_common_password(plain: str) -> bool`
  - `create_session_token(user_id: UUID, role: str, now: datetime | None = None) -> str` (HS256, claims `sub`, `role`, `iat`, `exp = iat + jwt_ttl_hours`)
  - `decode_session_token(token: str) -> SessionClaims | None`. `SessionClaims` is a frozen dataclass `(user_id: UUID, role: str)`. Returns `None` on bad signature, expiry or malformed input; never raises.
  - `normalize_email(raw: str) -> str` (strip + lower)
  - `normalize_phone(raw: str) -> str | None`: strip spaces, `-`, `(`, `)`; drop a leading `+91`, `91` when 12 digits, or `0` when 11 digits; return the 10 digits if they match `^[6-9]\d{9}$`, else `None`.

- [ ] **Step 1: Write the failing tests:**
  - hash round-trip true/false; the hash never equals the plain text
  - `is_common_password("password123") is True`
  - the token decodes to the same id and role
  - `decode_session_token` returns `None` for an expired token (pass `now` 9 h ago), a tampered signature and `"garbage"`
  - `normalize_phone`: `"+91 98765 43210"`, `"098765-43210"`, `"9876543210"` → `"9876543210"`; `"12345"` → `None`; `"5876543210"` → `None`
  - `normalize_email(" Prashant@Example.com ") == "prashant@example.com"`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `security.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit (Amit).** Suggested message: `feat(auth): argon2 hashing, signed session tokens and identifier normalisation`

---

### Task 4: Auth API, CSRF guard, role and object dependencies

**Files:**
- Create: `backend/app/core/deps.py`, `backend/app/core/ratelimit.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/auth.py`, `backend/app/api/auth.py`, `backend/app/api/rules.py`, `backend/app/api/dev.py`
- Modify: `backend/app/main.py` (mount routers, CSRF middleware, slowapi, security headers, CORS for `frontend_origin`)
- Test: `backend/tests/integration/test_auth.py`, `backend/tests/integration/test_rbac.py`

**Interfaces:**
- Consumes: Task 3 functions and Task 2 `User`/`get_db`.
- Produces endpoints:
  - `POST /api/auth/signup`, body `SignupIn{full_name: str 2..120, email: EmailStr | None, phone: str | None, password: str 8..128, preferred_locale: "en"|"hi"|"mr" = "en"}`. Unknown fields are ignored, so `role` cannot be set. → 201 `UserOut`, sets cookie. Errors: 422 `IDENTIFIER_REQUIRED` (neither email nor phone), `PHONE_INVALID`, `PASSWORD_TOO_COMMON`; 409 `ACCOUNT_EXISTS`.
  - `POST /api/auth/login`, body `LoginIn{identifier: str, password: str}`. The identifier is treated as a phone if `normalize_phone` succeeds, otherwise as an email. → 200 `UserOut`, sets cookie; 401 `INVALID_CREDENTIALS` (the same response for an unknown user or a wrong password); 429 `RATE_LIMITED` after 5 attempts per minute per IP+identifier.
  - `POST /api/auth/logout` → 204, clears the cookie.
  - `GET /api/auth/me` → `UserOut` or 401 `NOT_AUTHENTICATED`. An invalid cookie also returns 401 and a `Set-Cookie` that deletes it.
  - `GET /api/rules/settings` (roles `sales`, `admin`) → `[{key, value}]`, ordered by key.
  - `POST /api/dev/upload-probe` (mounted only when `env != "production"`; any signed-in user; multipart `file`) → `{"received_bytes": int}`. Used for Q-9.
- `UserOut{id, full_name, role, email: str | None, phone_masked: str | None ("••••••3210"), preferred_locale}`.
- `deps.py` produces:
  - `get_current_user(request, db) -> User` (401 `NOT_AUTHENTICATED` if missing, invalid or inactive)
  - `require_roles(*roles: str) -> Callable` (403 `FORBIDDEN`)
  - `get_owned_or_404(db, model, id, user)`, used from M4 on for object-level checks (404 `NOT_FOUND` when `homeowner_id != user.id` for homeowners)
- CSRF: middleware rejects unsafe methods under `/api` without `X-HF-CSRF: 1` → 403 `CSRF_HEADER_MISSING`.
- Security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

- [ ] **Step 1: Write the failing tests** in `test_auth.py`:
  - signup with email → 201; cookie `hf_session` is httpOnly and SameSite=Lax; `role == "homeowner"`
  - signup body containing `"role": "admin"` → user role is still `homeowner` (Review Focus 5)
  - signup `" Prashant@Example.com "`, then login with `"prashant@example.com"` → 200 (Review Focus 1)
  - signup with phone `"+91 98765 43210"`, then login with `"098765-43210"` → 200 (Review Focus 2)
  - duplicate email in a different case → 409 `ACCOUNT_EXISTS`
  - password `"password123"` → 422 `PASSWORD_TOO_COMMON`
  - no email and no phone → 422 `IDENTIFIER_REQUIRED`
  - wrong password and unknown user both → 401 `INVALID_CREDENTIALS` with identical bodies
  - 6th failed login within a minute → 429 `RATE_LIMITED`
  - `/me` with no cookie → 401; with a tampered cookie → 401 and the response deletes the cookie (Review Focus 3)
  - logout → 204, and `/me` afterwards → 401
  - POST signup without `X-HF-CSRF` → 403 `CSRF_HEADER_MISSING`
  - the 422 response body does not echo the submitted password
- [ ] **Step 2: Write the failing tests** in `test_rbac.py` (users created directly via the ORM with `hash_password`):
  - homeowner → `GET /api/rules/settings` → 403 `FORBIDDEN`
  - sales → 200; admin → 200
  - anonymous → 401
  - upload probe with a 9 MB body → `received_bytes == 9*1024*1024`
- [ ] **Step 3:** Run both files. Expected: FAIL.
- [ ] **Step 4:** Implement the schemas, deps, rate limiting (slowapi `Limiter`, key = client IP + normalised identifier for login), routers and middleware.
- [ ] **Step 5:** Run them. Expected: all PASS. Then run the full backend suite `uv run pytest -q`. Expected: all PASS.
- [ ] **Step 6: Commit (Amit).** Suggested message: `feat(auth): signup/login/logout/me with CSRF guard, rate limit and role checks`

---

### Task 5: Idempotent seed data

**Files:**
- Create: `backend/seed/__init__.py`, `backend/seed/__main__.py`, `backend/seed/data.py`
- Test: `backend/tests/integration/test_seed.py`

**Interfaces:**
- Produces: `seed.run(db: Session, demo_password: str) -> SeedReport`. `SeedReport` is a dataclass of created/skipped counts per table. Running it twice creates nothing the second time. Identity keys: user email, lead code, rule `(scheme_code, effective_from)` / `(min_kw, max_kw, effective_from)`, setting key.
- CLI: `uv run python -m seed` reads `SEED_DEMO_PASSWORD`, exits with code 1 and the message "SEED_DEMO_PASSWORD is not set" if missing, and prints the report.
- Data (values from spec; synthetic values marked):
  - Users: `sales@helioflow.example` (sales), `admin@helioflow.example` (admin), and homeowners `prashant@helioflow.example`, `rohit@helioflow.example`, `ayesha@helioflow.example`. Names are from the brief; phones are synthetic in the `9000000001…` range.
  - Settings, the seven keys and values from §3.7: `generation_kwh_per_kw_year=1400`, `roof_sqft_per_kw=100`, `min_monthly_bill_for_survey=1000`, `capacity_options_kw=[1..10]`, `usable_generation_pct="0.90"`, `default_fixed_charge_monthly=150`, `quote_option_offsets=[-1,0,1]`. Decimals are stored as JSON strings.
  - Price rule: 1–10 kW, ₹60,000, `gst_inclusive=true`, from 2026-01-01, open-ended, note "Placeholder (A-3). Client to confirm."
  - Subsidy rule: `CENTRAL_RESIDENTIAL`, `residential`, slabs `[{0,2,30000},{2,3,18000}]`, cap 78000, from 2024-02-13, open-ended, source note verbatim from §9.2.
  - Leads `LD-30881`, `LD-30902`, `LD-30915`, owned by the matching homeowner. They use the brief's ownership and monthly bill (3200 / 1900 / 650) with `status="draft"` and `score` null (scoring arrives in M2). Roof type `rcc_flat`, roof area, pincode `440010`/`440022`/`440013`, consent fields set, and `seed_note="Synthetic seed values: roof, pincode. Not from brief."`.
- [ ] **Step 1: Write the failing tests:** first run creates 5 users, 7 settings, 1 price rule, 1 subsidy rule and 3 leads; second run reports 0 created; the `sales@` password verifies against `demo_password`; `LD-30915.declared_monthly_bill == Decimal("650")`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `seed/`.
- [ ] **Step 4:** Run them. Expected: PASS. Then `SEED_DEMO_PASSWORD=<local value> uv run python -m seed` against dev, twice. Expected: the second run reports 0 created.
- [ ] **Step 5: Commit (Amit).** Suggested message: `feat(seed): idempotent demo users, rules, settings and brief sample leads`

---

### Task 6: Frontend scaffold, design tokens, brand assets

**Files:**
- Create via tooling: `frontend/` (`npx create-next-app@latest frontend --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm`), then `npx shadcn@latest init` and add components `button input label card badge skeleton sonner sheet dropdown-menu separator`.
- Create: `frontend/public/brand/helio-mark.png` (square crop of the supplied logo, 512 px), `frontend/app/icon.png`, `frontend/app/apple-icon.png`, `frontend/components/brand/logo.tsx`, `frontend/.env.example`
- Modify: `frontend/app/globals.css` (tokens), `frontend/next.config.ts`
- Source image: the logo the user supplied (copy it into `frontend/public/brand/`; do not edit the original).

**Interfaces:**
- Produces CSS variables (light theme only for M1; dark is out of scope):
  - `--hf-brand` = logo teal, **sampled from the image's background pixel** (expected ≈ `#006B63`)
  - `--hf-brand-ink` = white
  - `--hf-gold` = logo gold, sampled from the mark (expected ≈ `#E3B256`). Used only for brand moments (logo, the hero accent rule, the quote "payback" highlight later), never for warnings.
  - `--hf-bg` `#FFFFFF`, `--hf-surface` `#FAFAF9`, `--hf-border` `#E7E5E4`, `--hf-ink` `#1C1917`, `--hf-ink-2` `#57534E`
  - `--hf-attention` `#B45309` on `--hf-attention-bg` `#FEF3C7`; `--hf-error` `#B91C1C`

  These are mapped onto shadcn's `--primary`, `--ring`, etc., so shadcn components inherit the brand. Contrast of brand teal on white must be ≥ 4.5:1; verify with a quick computation in the step, and darken if needed.
- Produces `<Logo variant="mark" | "lockup" size?: number />`: the mark is the PNG in a 12 px rounded tile. The lockup is mark + "HelioFlow" wordmark (Inter 600) with the tagline as an optional second line.
- `next.config.ts`: `rewrites()` maps `/api/:path*` → `${process.env.BACKEND_URL}/api/:path*`. `headers()` adds the same three security headers as the backend. `BACKEND_URL` is server-only (no `NEXT_PUBLIC_`).

- [ ] **Step 1:** Scaffold with the commands above; record the installed Next.js major version in the task notes (it decides `middleware.ts` vs `proxy.ts` in Task 7).
- [ ] **Step 2:** With a scratchpad Python script (Pillow, run with `-I`), crop the supplied logo to the bounding square of the circle plus 12% padding, resize to 512, and print the sampled background and mark hex colours. Write the PNGs.
- [ ] **Step 3:** Write the tokens into `globals.css` using the sampled values, and the computed contrast ratio as a comment.
- [ ] **Step 4:** Build `logo.tsx`; replace the template home page with a temporary page that renders `<Logo variant="lockup" />`.
- [ ] **Step 5:** Run `npm run lint` and `npx tsc --noEmit`. Expected: 0 errors.
- [ ] **Step 6: Commit (Amit).** Suggested message: `feat(web): scaffold Next.js with HelioFlow tokens, shadcn and brand mark`

---

### Task 7: Locale routing en/hi/mr, switcher, translation parity check

**Files:**
- Create: `frontend/i18n/routing.ts`, `frontend/i18n/request.ts`, `frontend/i18n/navigation.ts`, `frontend/middleware.ts` **or** `frontend/proxy.ts` (whichever the installed Next major expects), `frontend/messages/en.json`, `hi.json`, `mr.json`, `frontend/scripts/check-i18n.mjs`, `frontend/components/language-switcher.tsx`
- Move: `frontend/app/layout.tsx` and `page.tsx` → `frontend/app/[locale]/layout.tsx`, `frontend/app/[locale]/page.tsx`

**Interfaces:**
- `routing = defineRouting({ locales: ["en","hi","mr"], defaultLocale: "en", localePrefix: "always" })`. Typed `Link`, `redirect`, `usePathname`, `useRouter` come from `i18n/navigation.ts`.
- The layout loads Inter and Noto Sans Devanagari via `next/font/google` (subsets latin + devanagari), sets `<html lang={locale}>`, and adds class `font-deva` with `line-height` +0.15 for `hi`/`mr`.
- `<LanguageSwitcher />` shows "English · हिन्दी · मराठी" as a compact dropdown, keeps the current path, and (once signed in) PATCHes the user's `preferred_locale`. **That PATCH endpoint arrives in M4; in M1 the switcher only changes the URL.**
- Message namespaces created in M1: `common` (appName "HelioFlow", tagline, language names), `auth` (sign-in labels, button, errors for every auth error code from Task 4), `errors` (all codes from Tasks 1 and 4: `NOT_FOUND`, `VALIDATION_ERROR`, `NOT_AUTHENTICATED`, `FORBIDDEN`, `CSRF_HEADER_MISSING`, `RATE_LIMITED`, `INVALID_CREDENTIALS`, `ACCOUNT_EXISTS`, `PASSWORD_TOO_COMMON`, `IDENTIFIER_REQUIRED`, `PHONE_INVALID`, `UNKNOWN`), `shell` (nav labels, empty states).
  - Tagline translations: hi "पहली पूछताछ से सौर ऊर्जा तक।", mr "पहिल्या चौकशीपासून सौर ऊर्जेपर्यंत." Mark them in a `_meta.reviewStatus: "needs-native-review"` key in hi/mr (A-26).
- `npm run check:i18n` runs `node scripts/check-i18n.mjs`, which exits 1 and lists missing or extra keys when the flattened key sets of `hi.json` and `mr.json` differ from `en.json` (ignoring `_meta`).

- [ ] **Step 1:** Write `check-i18n.mjs` first, then deliberately leave one key out of `mr.json`. Run `npm run check:i18n`. Expected: exit 1, naming the missing key.
- [ ] **Step 2:** Add the key back. Run again. Expected: exit 0.
- [ ] **Step 3:** Implement routing, the middleware/proxy file, the layout and the switcher.
- [ ] **Step 4:** Run `npm run dev`, then `curl -sI http://localhost:3000/` (expect a redirect to `/en`), `curl -sI http://localhost:3000/fr/sign-in` (expect 307/308 to `/en/...` or a 404 page, **not** 500; Review Focus 4), and `curl -s http://localhost:3000/hi | findstr "lang=\"hi\""`. Record the actual output.
- [ ] **Step 5:** Run `npm run lint`, `npx tsc --noEmit` and `npm run check:i18n`. Expected: all pass.
- [ ] **Step 6: Commit (Amit).** Suggested message: `feat(i18n): en/hi/mr locale routing, Devanagari type and language switcher`

---

### Task 8: Frontend auth flow and role shells through the proxy

**Files:**
- Create: `frontend/lib/api.ts`, `frontend/lib/query-client.tsx`, `frontend/lib/use-session.ts`, `frontend/app/[locale]/sign-in/page.tsx`, `frontend/app/[locale]/(homeowner)/my/page.tsx`, `frontend/app/[locale]/(staff)/staff/layout.tsx`, `frontend/app/[locale]/(staff)/staff/leads/page.tsx`, `frontend/components/site-header.tsx`, `frontend/components/server-waking.tsx`
- Modify: `frontend/app/[locale]/page.tsx` (landing), `frontend/app/[locale]/layout.tsx` (providers, header)

**Interfaces:**
- `api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T>`. Always relative `/api…`, `credentials: "same-origin"`, adds `X-HF-CSRF: 1` on unsafe methods, and on a non-2xx response throws `ApiError{status, code, message}` (code from the body, else `UNKNOWN`).
- `useSession()` is a TanStack Query wrapper over `GET /api/auth/me` returning `{ user: UserOut | null, isLoading }`. A 401 resolves to `user: null`, not an error.
- Landing `/[locale]`: lockup, tagline, one sentence of value, and a primary button "Check if solar fits your home" → `/[locale]/sign-in?next=/my` in M1, re-pointed to the lead form in M4 (no dead buttons). A secondary "Staff sign in" link.
- Sign-in page: react-hook-form + zod (identifier required, password ≥ 8). Loading state on the button. API errors map to `t("errors."+code)`. On success, redirect by role: homeowner → `next` or `/my`; sales/admin → `/staff/leads`.
- `/my` (homeowner) and `/staff/leads` (sales/admin): real shells with a proper empty state (icon, one sentence, no fake data). The page redirects to sign-in if `user` is null, and the staff layout shows a 403 view for homeowners. Each guard redirects **once** (Review Focus 3).
- `<ServerWaking />`: if `/api/health` takes more than 2.5 s, shows "Waking up the server…" with a subtle progress bar; hides on success; shows an error with a retry button after 60 s.

- [ ] **Step 1:** Implement `api.ts`, `use-session.ts`, providers, the header (logo, switcher, sign-out when signed in), landing, sign-in and the two shells.
- [ ] **Step 2:** Run the backend `uv run uvicorn app.main:app --port 8000` with `COOKIE_SECURE=false`, and `BACKEND_URL=http://localhost:8000 npm run dev`.
- [ ] **Step 3: Verify manually through the proxy** and record the results:
  1. Sign in as `sales@helioflow.example` → lands on `/en/staff/leads`. The cookie is visible in devtools as httpOnly for `localhost:3000`.
  2. Sign out, then sign in as `prashant@helioflow.example` in `/hi` → lands on `/hi/my` with Hindi labels.
  3. As a homeowner, open `/en/staff/leads` → 403 view, no loop.
  4. Delete the cookie value by hand (set it to `x`) and reload `/en/my` → exactly one redirect to sign-in.
  5. Upload probe through the proxy: `curl` a 9 MB file to `http://localhost:3000/api/dev/upload-probe` with the session cookie and CSRF header → `received_bytes` = 9437184. Note the result for Q-9; the Vercel limit itself is checked at deploy in M7.
  6. At phone width (375 px) in devtools, landing and sign-in have no horizontal scroll and tap targets are ≥ 44 px.
- [ ] **Step 4:** Run `npm run lint`, `npx tsc --noEmit`, `npm run check:i18n` and `npm run build`. Expected: all pass.
- [ ] **Step 5: Commit (Amit).** Suggested message: `feat(web): sign-in through API proxy, role-aware shells and server wake-up state`

---

### Task 9: CI workflow, spec touch-ups, M1 verification report

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `docs/ARCHITECTURE.md` (§3.2 add `seed_note`; §20 replace "Brand (deep green) #166534" with the sampled logo teal and add the gold rule from Task 6)

**Interfaces:**
- CI on push and pull_request, two jobs:
  - `backend`: service `postgres:16-alpine` (user/password/db `helio`/`helio`/`helio_test`), `astral-sh/setup-uv`, `uv sync --frozen`, `uv run ruff check .`, `uv run pytest -q` with env `TEST_DATABASE_URL`, `DATABASE_URL`, `JWT_SECRET=ci-only-not-secret`, `ENV=test`.
  - `frontend`: Node 22, `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm run check:i18n`, `npm run build` with `BACKEND_URL=http://localhost:8000`.
- [ ] **Step 1:** Write `ci.yml`. Validate the YAML locally (`uv run python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/ci.yml'))"` after adding pyyaml to dev deps, or use `npx yaml-lint`).
- [ ] **Step 2:** Make the two doc edits.
- [ ] **Step 3:** Run the full local verification from a clean state: `docker compose down -v && docker compose up -d db`, `uv run alembic upgrade head`, `uv run python -m seed`, `uv run pytest -q --cov=app`, then the frontend `lint`/`tsc`/`check:i18n`/`build`. Paste the real outputs into the milestone report.
- [ ] **Step 4: Milestone report to Amit:** what was built, the list of files, real test output, known issues (CI is unverified until the first push; the Vercel body limit is unverified until deploy), and the commit-message list. Then ask Amit to run `git config user.name` and `git config user.email` before the first commit, and to run `git init` personally if the repo isn't initialised yet. **Stop and wait for review.**
