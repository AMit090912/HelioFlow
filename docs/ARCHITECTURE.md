# HelioFlow — Architecture (Revision 3)

**From First Lead to Solar Power.**

| | |
|---|---|
| Status | Revision 3 for final approval. No application code has been written. |
| Changes in Rev 3 | (1) Hindi and Marathi are mandatory for the whole homeowner journey (§2, §13, §20, §21). (2) Sample-lead sizes are labelled *provisional*; final sizing and all quote options respect verified roof capacity and sanctioned load (§8, §10.1, §18). (3) `citext` extension added; `bill_readings.bill_file_id` is unique (§3, §16). (4) Quote snapshot is immutable, but lifecycle fields change through controlled transitions (§3.8, §11). |
| Owner | Amit |
| Client | Company A, Nagpur (rooftop solar, Vidarbha) |
| Scope | Assignment CORE BUILD plus the depth requested in the owner's revision notes |
| Labels | **[A-n]** assumption (see §17) · **[Q-n]** open question (see §19) · **[CLIENT]** stated by the client in the brief |

---

## 1. Architecture and technology stack

```
 Homeowner phone / staff desktop
          │ HTTPS, one origin
          ▼
 ┌──────────────────────── Vercel ────────────────────────┐
 │ Next.js (App Router, TypeScript)                       │
 │ Tailwind CSS · shadcn/ui · TanStack Query · next-intl  │
 │ next.config rewrites:  /api/*  →  BACKEND_URL/*         │
 └───────────────────────────┬────────────────────────────┘
                             │ proxied HTTPS
 ┌──────────────────────── Render ────────────────────────┐
 │ FastAPI (Python 3.12)                                   │
 │  api/        routers: auth, leads, bills, quotes,       │
 │              projects, status, rules, notifications     │
 │  core/       config, security (JWT, argon2), RBAC deps  │
 │  services/                                              │
 │    calc/     PURE functions, Decimal, no I/O, no AI     │
 │    uploads/  signature check, PDF/image processing      │
 │    ai/       Groq → Gemini → manual, schema validation  │
 │    pdf/      ReportLab quote renderer                   │
 │    notify/   simulated WhatsApp/SMS outbox              │
 │  models/     SQLAlchemy 2.x   schemas/  Pydantic v2     │
 └───────────────────────────┬────────────────────────────┘
                             │ SQLAlchemy + Alembic
                   PostgreSQL (Neon free tier)
     Outbound from FastAPI only: Groq API, Gemini API
```

### Decisions

| Decision | Reason |
|---|---|
| Only FastAPI talks to the database and the AI providers | API keys stay on the server, and every rule is enforced in one place. The browser cannot bypass validation. |
| Next.js rewrites `/api/*` to FastAPI | The browser sees one origin, so the session cookie can be **httpOnly** without cross-site cookie problems (Safari/ITP) or CORS. |
| Calculation engine is pure functions | Rules and inputs go in, results come out. It is unit-testable without a database and has **no AI dependency**. |
| Python `Decimal` for all money and ratios | Floats give wrong answers on exact boundaries, e.g. `4200/1400` must be exactly `3`. |
| Bill extraction runs as a background task, and the browser polls | Upload returns `202` with a reading id at once. The browser polls `GET /bills/{id}` every ~1.5 s. This avoids proxy and request timeouts during a chain of up to ~50 s (Groq, then Gemini), and lets the UI show real progress steps. *This changes Revision 1, which ran extraction synchronously.* |
| No queue or worker service | ~1,400 leads/month **[CLIENT]** is ~50 a day. FastAPI `BackgroundTasks` on one instance is enough. Readings left in `processing` for more than 2 minutes (e.g. after a restart) are marked `failed`, and the user gets manual entry. |

### Stack (approved)

| Layer | Technology |
|---|---|
| Frontend | Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, next-intl, react-hook-form + zod, browser-image-compression |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, pwdlib/argon2, a small in-memory sliding-window rate limiter (its key needs the login identifier from the request body) |
| Files | Pillow (images), **pypdf** (text extraction, encryption detection), **pypdfium2** (rendering scanned pages). PyMuPDF is avoided because of its AGPL licence. |
| AI | Groq vision/text models (primary), Gemini Flash (fallback), manual entry (final fallback). Model names come from environment variables. |
| PDF output | ReportLab |
| Database | PostgreSQL (Neon), extension `btree_gist` for date-overlap constraints |
| Tests | pytest, httpx TestClient, Playwright, GitHub Actions |
| Deploy | Vercel (frontend), Render (backend), Neon (database) |

### Repository layout

```
/backend    app/{api,core,models,schemas,services/{calc,uploads,ai,pdf,notify}}
            alembic/  seed/  tests/{unit,integration,fixtures}
/frontend   app/[locale]/{(public),(homeowner),(staff)}/…  components/{ui,…}
            lib/  messages/{en,hi,mr}.json  e2e/
/docs       ARCHITECTURE.md  TDD source  deployment.md
.github/workflows/ci.yml
```

---

## 2. Screens (8 core + 1 admin)

| # | Screen | Who | What it does |
|---|---|---|---|
| 1 | **Get solar**: 3-step lead form | Homeowner | Step 1: owner/tenant, home/business **[Q-5]**, roof type, roof area, monthly bill, pincode. Step 2: create account. Step 3: bill upload (image or PDF), with consent checkbox. |
| 2 | **Check your bill** | Homeowner | Bill preview on the left, extracted values on the right (stacked on phones). Low-confidence or flagged fields are highlighted. Actions: *Confirm*, *Edit*, *Upload again*. Manual-entry form if the AI fails. |
| 3 | **My solar**: homeowner dashboard | Homeowner | Next step only: "Survey visit: we'll schedule it" (High) or "We'll call you first" (Low). Also recommended size, quote card when sent, project card when started. **The score label is never shown to the homeowner.** |
| 4 | **Your quote** | Homeowner | A story in three numbers: **size → cost after subsidy → payback (estimate)**. Then options, a breakdown, assumptions, *Download PDF* and *Accept quote*. |
| 5 | **Project status**: public token link | Anyone with the link | Stage timeline and dates. No consumer number, address, phone, money or bill. |
| 6 | **Leads inbox** | Sales | High first, then newest. Shows score, reasons, recommended kW, next action and flags (sanctioned load, unverified bill). Filters: score, status. Becomes cards on phones. |
| 7 | **Lead detail and quote builder** | Sales | Bill preview with AI vs confirmed values, score reasons, survey inputs (measured roof area, notes), and a quote builder with live calculations and overrides (§10). Actions: *Send quote*, *Record advance (simulated)*. |
| 8 | **Projects** | Sales | Table with stage and days in stage. Detail drawer: advance stage, event history, copy/regenerate/revoke status link, simulated notifications. |
| 9 | **Rules and settings** | Admin **[Q-7]** | Price rules, subsidy rules (with effective dates) and settings (§3.6). Validation and overlap errors appear inline. |

Sign-in and sign-out are utility pages and not counted.

### Languages (mandatory for the homeowner journey)

- **Every homeowner-facing surface is available in English, हिन्दी and मराठी:** screens 1–5, sign-in/sign-up, all validation, error, empty and loading messages, upload and re-upload tips, the consent text, the quote PDF (§10, §Q-14) and simulated notification texts (§13).
- **Language switcher** in the homeowner header and on the public status page. Locale is in the URL (`/hi/...`, `/mr/...`, `/en/...` via next-intl routing). The first visit uses the `Accept-Language` header, defaulting to English. The choice is saved to `users.preferred_locale` after sign-up, so notifications and PDFs use it.
- **The API returns error codes, not sentences** (e.g. `PDF_PASSWORD_PROTECTED`, `BILL_BELOW_THRESHOLD`). The frontend maps codes to `messages/{en,hi,mr}.json`, so every backend error is translated.
- Numbers stay in Western digits with Indian grouping (₹1,02,000) in all three languages **[A-27]**.
- A CI check fails if any key in `en.json` is missing from `hi.json` or `mr.json`.
- Staff screens (6–9) are English **[A-28]**. Customer names and data appear exactly as entered.
- Translations are drafted by the developer with AI help and marked for **native-speaker review before launch** **[A-26]**.

### Homeowner journey

```
Screen 1 ─ details ─ account ─ upload ─► Screen 2 (polls: checking file → reading bill → done)
   │ AI ok   → confirm/edit values ───────────────┐
   │ poor    → "Upload a clearer photo" + tips    │
   │ AI fail → manual entry (lead kept, flagged)  │
   ▼                                              ▼
Screen 3: score + recommendation computed from CONFIRMED values
   High → "survey visit" · Low → "we'll call you" · tenant → "we'll call you"
   ▼ (after survey, sales sends quote)
Screen 4: accept → Screen 3 shows "advance pending" → sales records advance
   ▼
Project created → Screen 3 project card + Screen 5 link (also sent as simulated WhatsApp)
```

### Sales journey

```
Screen 6 inbox → Screen 7 lead
   High → visit → enter survey data · Low → call → may upgrade to visit (reason stored)
   → build quote (options recalculate live) → Send (snapshot frozen, simulated message)
   → homeowner accepts → Record advance (amount + simulated reference) → project created
Screen 8 → advance stages → each change writes an event and a simulated notification
```

### Lead status machine

`draft → bill_processing → bill_review → qualified → (survey_pending | call_pending) → surveyed → quoted → accepted → converted`

Sales may move `call_pending → survey_pending` with a reason. Nothing ever moves a lead to "rejected" automatically. `closed_lost` is set only by a person, with a reason.

---

## 3. Database schema

Twelve tables. Every table has `id uuid pk` and `created_at timestamptz`. Money is stored as `numeric(12,2)` in rupees, kW as `numeric(5,2)`, and ratios as `numeric(6,4)`.

The first Alembic migration starts with:

```sql
CREATE EXTENSION IF NOT EXISTS citext;      -- case-insensitive email column (§3.1)
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- effective-date overlap constraints (§3.5, §3.6)
```

Both extensions are supported on Neon and standard PostgreSQL. CI runs the same migration against a clean Postgres container.

### 3.1 `users`
| Column | Type / constraint |
|---|---|
| role | enum `homeowner \| sales \| admin` **[Q-7]** |
| full_name | text, not null |
| email | `citext`, unique, nullable (needs the `citext` extension, created in the first migration) |
| phone | text, unique, nullable, check `^[6-9]\d{9}$` (Indian mobile) |
| password_hash | text (argon2id) |
| preferred_locale | enum `en \| hi \| mr`, default `en` |
| is_active | bool |

Check: at least one of email or phone must be set. Staff accounts are **seeded or admin-created only**; self sign-up always creates a `homeowner`.

### 3.2 `leads`
| Column | Notes |
|---|---|
| code | `LD-30881` style, unique |
| homeowner_id → users | idx |
| ownership | enum `owner \| tenant` |
| property_type | enum `home \| business` **[Q-5]** |
| roof_type | enum `rcc_flat \| metal_sheet \| tiled \| other` **[A-14]** |
| roof_area_sqft | numeric, check > 0 |
| declared_monthly_bill | numeric, check > 0 (what the homeowner typed) |
| pincode | char(6), check `^[1-9]\d{5}$` |
| address | text, nullable (personal data) |
| consent_at, consent_version | not null, set at submission |
| status | enum (§2) |
| score | enum `high \| low`, nullable until qualified |
| score_reasons | jsonb, e.g. `[{"code":"tenant"},{"code":"bill_below_threshold","value":650,"threshold":1000}]` |
| recommended_kw | numeric, nullable (null for tenants or missing data) |
| sizing_detail | jsonb: required_kw_exact, kw_by_usage, kw_by_roof, sanctioned_load_flag |
| next_action | enum `survey_visit \| call` |
| verified_roof_area_sqft, roof_verified_via (`survey \| call`), roof_verified_by, roof_verified_at | roof capacity confirmed by staff; required before a quote (§8) |
| survey_notes, surveyed_at, surveyed_by | survey inputs |
| current_bill_reading_id → bill_readings | nullable |
| seed_note | text, nullable. Labels synthetic seed values that are not from the brief (§8.1). Null for real leads. |

Indexes: `(status, score, created_at desc)` for the inbox, and `(homeowner_id)`.

### 3.3 `bill_files`: stored uploads, one row per upload
| Column | Notes |
|---|---|
| lead_id → leads | idx |
| kind | enum `image \| pdf` |
| mime, size_bytes, sha256, page_count | sha256 indexed together with lead_id |
| content | bytea (sanitised image or original PDF), **deferred load** |
| preview_png | bytea (re-encoded image, or page 1 of a PDF rendered at 150 DPI), deferred |

Kept separate from `bill_readings` so that moving to object storage later changes only this table, which would then hold a key instead of bytes.

### 3.4 `bill_readings`: exactly one extraction per file
| Column | Notes |
|---|---|
| lead_id | FK, idx |
| bill_file_id | FK, **`UNIQUE`**: enforces the 1–1 relationship with `bill_files` |
| status | enum `processing \| needs_reupload \| needs_review \| confirmed \| failed_manual` |
| quality | jsonb (dimensions, brightness, edge-variance score, reason codes) |
| source_path | enum `pdf_text \| vision \| manual` |
| attempts | jsonb array `[{provider, model, prompt_version, started_at, ms, outcome, error_code}]` |
| provider, model, prompt_version | the attempt that succeeded |
| ai_values | jsonb, **immutable after write**: `{field: {value, confidence}}` plus `is_electricity_bill`, `legibility` |
| validation_flags | jsonb (sanity-rule results) |
| consumer_number, tariff_category, sanctioned_load_kw, monthly_units (int[]), avg_monthly_units, bill_amount, fixed_charge_monthly | **typed, human-confirmed values** |
| edited_fields | text[] (where the person changed the AI's value) |
| confirmed_by, confirmed_at | |

`ai_values` (what the AI said) and the typed columns (what a person confirmed) are never merged. This preserves the audit trail and gives accuracy data.

### 3.5 `price_rules`
`min_kw`, `max_kw`, `price_per_kw`, `gst_inclusive bool`, `effective_from date`, `effective_to date null`, `note`, `created_by`

```sql
EXCLUDE USING gist (
  numrange(min_kw, max_kw, '[]') WITH &&,
  daterange(effective_from, coalesce(effective_to, 'infinity'), '[]') WITH &&)
```

### 3.6 `subsidy_rules`
`scheme_code`, `segment` (enum `residential`), `slabs jsonb [{from_kw,to_kw,amount_per_kw}]`, `cap_amount`, `effective_from`, `effective_to null`, `source_note` ("Client-provided, illustrative. Verify against official scheme before launch."), `created_by`

```sql
EXCLUDE USING gist (scheme_code WITH =, segment WITH =,
  daterange(effective_from, coalesce(effective_to,'infinity'), '[]') WITH &&)
```

Slabs are validated by Pydantic: contiguous, starting at 0, non-negative.

### 3.7 `settings`
Key/value (`key text pk`, `value jsonb`, `updated_by`, `updated_at`), validated by a Pydantic model per key.

| Key | Initial value |
|---|---|
| `generation_kwh_per_kw_year` | 1400 **[CLIENT]** |
| `roof_sqft_per_kw` | 100 **[A-2]** |
| `min_monthly_bill_for_survey` | 1000 **[A-1]** |
| `capacity_options_kw` | [1,2,3,4,5,6,7,8,9,10] **[A-9]** |
| `usable_generation_pct` | 0.90 **[A-6]** |
| `default_fixed_charge_monthly` | 150 **[A-8]** |
| `quote_option_offsets` | [-1, 0, +1] **[A-10]** |

Settings are not date-versioned. Every quote and score stores the values it used, which is sufficient for audit.

### 3.8 `quotes`: immutable content, controlled lifecycle

| Column | Kind | Notes |
|---|---|---|
| number | immutable | `HF-Q-2026-000123`, unique |
| lead_id → leads | immutable | idx |
| priced_on | immutable | date used to select rules |
| snapshot | immutable | jsonb (§11): inputs, rules, settings, options, results |
| calc_version | immutable | e.g. `calc-1.0.0` |
| created_by, sent_at | immutable | |
| status | **lifecycle** | `sent \| accepted \| superseded` |
| selected_kw | **lifecycle** | set once, on acceptance; must be one of the snapshot's options |
| accepted_at, accepted_by | **lifecycle** | set once, on acceptance |
| superseded_at, superseded_by_quote_id | **lifecycle** | set once, when a newer quote replaces this one |

The quote's **commercial content never changes after sending**. Only lifecycle metadata changes, and only through these transitions:

| From | To | Who | Allowed when |
|---|---|---|---|
| `sent` | `accepted` | Homeowner who owns the lead | Not superseded; `selected_kw` ∈ snapshot options |
| `sent` | `superseded` | System, when sales sends a new quote for the same lead | Automatic, in the same transaction as the insert |
| `accepted` | — | — | Terminal. A change after acceptance requires a person to issue a new quote. |

Enforcement is in two layers:
1. **Service layer:** a single `transition_quote()` function holds the state machine, checks permissions and writes the timestamps.
2. **Database trigger `quotes_guard`:** rejects any `UPDATE` that changes an immutable column, any transition not in the table above, or any change to `selected_kw`, `accepted_at` or `superseded_at` once set. This holds even if application code has a bug or someone runs a manual SQL update.

A partial unique index `ON quotes(lead_id) WHERE status = 'sent'` guarantees only one open quote per lead.

### 3.9 `projects`
`lead_id unique`, `quote_id`, `stage` (enum, §12), `stage_changed_at`, `advance_amount`, `advance_reference` ("SIMULATED-…"), `status_token_hash char(64) unique null`, `status_token_created_at`, `status_token_revoked_at`. Index `(stage, stage_changed_at)`.

### 3.10 `project_events`
`project_id`, `from_stage`, `to_stage`, `actor_id`, `note`, `created_at`. Append-only; this is both the timeline and the audit log.

### 3.11 `notifications`: simulated outbox
`project_id null`, `lead_id`, `type` (`quote_sent \| stage_changed \| status_link`), `channel` (`whatsapp \| sms`), `recipient_masked` (`+91 ••••• •4821`), `message`, `delivery_status` (`simulated`), `created_at`.

### 3.12 Relationships

```
users 1─* leads 1─* bill_files 1─1 bill_readings
                 └─* quotes 1─0..1 projects 1─* project_events
                 └─* notifications *─0..1 projects
price_rules, subsidy_rules, settings  ← read by calc; copied into quote snapshots
```

---

## 4. Authentication and authorisation

| Item | Design |
|---|---|
| Sign-up | Homeowners only, during lead form step 2: name, phone and/or email, password (min 8 characters, checked against a short common-password list). |
| Sign-in | Phone or email plus password. Real OTP is not built. |
| Hashing | argon2id (pwdlib). |
| Session | JWT (HS256, `sub`, `role`, `exp` = 8 h), in cookie `hf_session`: httpOnly, Secure, SameSite=Lax, Path=/. Lax is used because Strict would make a staff member following a link look signed out. |
| CSRF | SameSite=Lax, plus every unsafe method must send the header `X-HF-CSRF: 1`. A cross-site form cannot set custom headers. |
| Role checks | FastAPI dependencies `require_roles("sales","admin")`. Next.js middleware redirects by cookie presence **for UX only**. The API is the real gate. |
| Object-level | Every homeowner query is filtered by `homeowner_id = current_user.id`. A missing or foreign record returns **404** (not 403), so record existence is not leaked. |
| Rate limits | Login 5/min per IP+identifier, upload 10/hour per user, status page 30/min per IP. In-memory: fine for one instance, documented. |

### Permission matrix

| Action | Homeowner | Sales | Admin |
|---|---|---|---|
| Create lead, upload bill, confirm values | own | — | — |
| View lead and bill | own | all | all |
| Score override, survey, quote, record advance | — | ✓ | ✓ |
| View and accept quote | own | view | view |
| Advance project stage, manage status link | — | ✓ | ✓ |
| Edit rules and settings | — | view | ✓ |

---

## 5. Bill upload architecture

### 5.1 Acceptance gate (synchronous, before anything is stored)

| Check | Rule | User-facing message |
|---|---|---|
| Size | ≤ 10 MB (env `MAX_UPLOAD_MB`), enforced while streaming | "This file is larger than 10 MB." |
| Signature | Magic bytes: `%PDF-`, `FF D8 FF` (JPEG), `89 50 4E 47` (PNG), `RIFF....WEBP`. The extension and `Content-Type` are ignored. | "We accept PDF, JPG, PNG or WebP." |
| Image decode | Pillow `verify()`, then full load; `MAX_IMAGE_PIXELS` = 40 MP (decompression-bomb guard) | "This image could not be opened." |
| Image re-encode | Fix orientation from EXIF, then save a fresh JPEG/PNG **without metadata** (removes GPS) | — |
| PDF open | pypdf. Encrypted → reject. Parse error → reject. Pages > 20 → reject. | "This PDF is password-protected. Please upload an unlocked copy or a photo." / "This PDF seems damaged." |
| Duplicate | sha256 already uploaded **for the same lead** → reuse the existing reading (no new AI call). Never shared across users. | — |

The client compresses phone photos to ≤ 2 MB and 2,000 px before upload. HEIC is not accepted; iOS Safari normally converts it to JPEG for web uploads **[A-17]**.

### 5.2 PDF routing

```
PDF ─► pypdf extract text per page (first 5 pages max)
        ├─ text-based: ≥ 200 chars and contains bill keywords (units|kWh|consumer|sanctioned|tariff)
        │     → choose pages with the highest keyword score (max 2)
        │     → TEXT path: Groq text model → Gemini → manual
        └─ scanned: little/no text
              → render pages 1–2 with pypdfium2 at 200 DPI (≤ 2,500 px long side)
              → quality gate per page → VISION path
```

Only the 1–2 most relevant pages ever leave the server, never the whole PDF.

### 5.3 Image quality gate (deterministic, runs before any AI call)

| Signal | Initial threshold **[A-16]** | Failure reason shown |
|---|---|---|
| Short side | ≥ 700 px | "Photo is too small. Move closer." |
| Mean brightness | 40–235 (0–255) | "Too dark" / "Too bright. Avoid flash glare." |
| Edge variance (Pillow `FIND_EDGES` variance) | ≥ calibrated value from fixtures | "Photo looks blurry. Hold steady and tap to focus." |

The model's own `legibility = poor` or `is_electricity_bill = false` also leads to a re-upload request.

### 5.4 Storage

- Files go in Postgres `bytea` (`bill_files`) and are served only by `GET /api/bills/{id}/preview`, which is authenticated and object-checked.
- Responses carry `Cache-Control: private, no-store`, `Content-Disposition: inline` for the PNG preview and `attachment` for the original PDF, plus `X-Content-Type-Options: nosniff`.
- The browser always views the **PNG preview**. Original PDFs are never rendered in-page.
- **Limitation:** Neon's free tier storage is small (about 0.5 GB; verify current limits). At ~1–2 MB per upload that is a few hundred bills. Database backups grow with files. The production path is S3/R2 with private buckets and signed URLs; only `bill_files` changes **[A-12]**.

---

## 6. AI extraction and fallback

### 6.1 Output schema (Pydantic, strict)

```json
{
  "is_electricity_bill": true,
  "legibility": "good|fair|poor",
  "consumer_number":    {"value": "string|null", "confidence": 0.0},
  "tariff_category":    {"value": "string|null", "confidence": 0.0},
  "sanctioned_load_kw": {"value": "number|null", "confidence": 0.0},
  "monthly_units":      {"value": [{"month": "YYYY-MM", "units": 0}], "confidence": 0.0},
  "current_units":      {"value": "integer|null", "confidence": 0.0},
  "bill_amount":        {"value": "number|null", "confidence": 0.0},
  "fixed_charge":       {"value": "number|null", "confidence": 0.0},
  "billing_days":       {"value": "integer|null", "confidence": 0.0},
  "previous_reading":   {"value": "number|null", "confidence": 0.0},
  "present_reading":    {"value": "number|null", "confidence": 0.0},
  "meter_multiplier":   {"value": "number|null", "confidence": 0.0},
  "arrears":            {"value": "number|null", "confidence": 0.0},
  "total_due":          {"value": "number|null", "confidence": 0.0}
}
```

The prompt instructs the model to return `null` when a value is not visible and **never to guess**, including masked or redacted digits. `fixed_charge` is extracted when it is printed, to support §10.

**Prompt `bill-v2` (after real spot-bill samples).** Indian bills are not always monthly A4 bills. Thermal "bill-cum-notice" receipts (e.g. TSSPDCL) often cover 60–93 days and print several amounts. The fields added in v2 exist only to get the **same calculation inputs** right; no new form fields are asked of the homeowner.
- `bill_amount` is **this period's charges** (BILL AMOUNT), never TOTAL DUE or anything including arrears. `arrears` and `total_due` are read only to catch that mistake (flag `may_include_arrears`).
- `billing_days` lets a multi-month bill be converted to an average month **[A-30]**: units, bill and fixed charge are each × (365/12) ÷ days. Example: 1,737 units over 93 days → 568.1 units/month.
- `previous_reading`/`present_reading`/`meter_multiplier` cross-check the units (flag `units_mismatch_readings`) and supply them when they aren't printed.
- Labels it maps include: USC / SC.NO → consumer number; CONTRACTED LOAD → sanctioned load; CAT → tariff; CUST CHARGES → fixed charge.
- A provider answering `"field": null` instead of `{"value": null}` is accepted (Gemini does this).
- Live-checked on the user's sample bills (Groq and Gemini): every calculation input read correctly, and masked consumer numbers returned as null.

### 6.2 Provider chain

```
for provider in [Groq, Gemini]:            # models from env
    try: call (temperature 0, JSON mode / response schema, timeout 20 s)
         on 429/5xx/timeout: 1 retry with backoff (honour Retry-After ≤ 5 s), then next provider
         parse → Pydantic validate → on invalid JSON/schema: record, next provider
         success → stop
    except network errors → record, next provider
all failed → status failed_manual → homeowner sees the manual entry form; lead saved, flagged "bill not AI-read"
```

Every attempt is recorded in `bill_readings.attempts`. Raw provider responses are stored without being logged to stdout.

**Models in use** (env-configurable, verified against the live accounts on 2026-11-03):

| Path | Primary (Groq) | Fallback (Gemini) |
|---|---|---|
| Photo or scanned PDF (vision) | `qwen/qwen3.8-27b` (accepts images; the Llama vision models were not available on this account) | `gemini-2.5-flash` |
| Text PDF | `openai/gpt-oss-120b` | `gemini-2.5-flash` |

**Live check on the synthetic sample bill** (`scripts/live_bill_check.py`): all three paths read all six fields correctly with confidence 1.0 (Groq vision 2.4 s including one real rate-limit retry, Groq text 1.7 s, Gemini 6.0 s). Groq is fronted by Cloudflare, which rejects default library user agents, so every request sends an explicit `User-Agent`.

### 6.3 Sanity validation (deterministic, after the AI)

| Rule | Action if violated |
|---|---|
| Monthly units 0–5,000 per month | Field flagged, must be reviewed |
| Sanctioned load 0.1–100 kW | Flagged |
| Consumer number contains only digits, 9–15 long **[A-18]** | Flagged (soft; not a rejection) |
| Implied ₹/unit = bill ÷ units outside 2–25 | Flagged |
| Extracted bill amount differs from the declared bill by more than 30% | Flagged ("Bill amount differs from what you entered") |
| Any field confidence < 0.7 | Highlighted for review |

**Average monthly units** = mean of the `monthly_units` history if there are ≥ 3 months, otherwise `current_units`. The method used is stored.

### 6.4 Human verification

- The homeowner confirms or edits. The typed columns are set, and `edited_fields` records the differences.
- Sales sees the AI value next to the confirmed value with an "edited by customer" marker, and can re-edit with a reason.
- Scoring and sizing run **only on confirmed values**, never on raw AI output.

### 6.5 Modes (env `AI_MODE`)

| Mode | Behaviour |
|---|---|
| `live` | Real Groq → Gemini. Default in production. |
| `demo` | Deterministic fixtures for the seeded synthetic bills only. A **"Demo mode: AI simulated"** banner is shown on every bill screen. Never the default. |
| `test` | Mock providers injected in pytest and Playwright, including failure scripts (Groq 429 → Gemini OK, both fail, invalid JSON). |

---

## 7. Lead scoring

Scoring is deterministic and runs on confirmed values plus form answers. Thresholds are read from `settings`.

```
reasons = []
if ownership == tenant:                              reasons += tenant
bill = confirmed bill_amount ?? declared_monthly_bill
if bill < min_monthly_bill_for_survey (₹1,000 [A-1]): reasons += bill_below_threshold
if roof capacity < 1 kW (§8):                        reasons += roof_too_small      [A-15]
if avg_monthly_units is missing:                     reasons += usage_unknown       [A-15]

score       = LOW if reasons else HIGH
next_action = call if LOW else survey_visit
informational flags (do NOT change score): exceeds_sanctioned_load, bill_not_ai_verified, extraction_flags
```

- A Low score never rejects a lead **[CLIENT]**. It only swaps the visit for a call.
- Sales can override Low to High after the call. The override reason and actor are stored in `score_reasons`.
- The threshold value used is stored with each reason (e.g. `{"code":"bill_below_threshold","value":650,"threshold":1000}`), so later threshold edits don't rewrite history.
- The bill used for the threshold is the **confirmed bill amount** when available, otherwise the declared amount (the source is stored).

---

## 8. Solar recommendation

**Formulas** (G = `generation_kwh_per_kw_year` = 1,400 **[CLIENT]**, R = `roof_sqft_per_kw` = 100 **[A-2]**):

```
annual_units     = avg_monthly_units × 12
required_kw      = annual_units ÷ G                      (exact Decimal)
kw_by_usage      = smallest capacity option ≥ required_kw   (ceil to configured whole-kW option)
kw_by_roof       = largest capacity option ≤ roof_area ÷ R
recommended_kw   = min(kw_by_usage, kw_by_roof)          (if ≥ smallest option, else none)
tenant           → recommended_kw = none
units missing    → recommended_kw = none (reason usage_unknown)
sanctioned_load < recommended_kw → flag exceeds_sanctioned_load (NOT capped) [owner revision]
```

**Rounding:** `required_kw` keeps full precision. Rounding up happens only when choosing the option, so exactly 350 units/month gives `4200 ÷ 1400 = 3` and therefore **3 kW, not 4**.

### Provisional vs final recommendation

| Stage | Roof input used | Label | Used for |
|---|---|---|---|
| **Provisional** | Homeowner's *declared* roof area, or none if missing | "Provisional: roof not yet verified" | Scoring, the homeowner dashboard ("about 3 kW"), the inbox |
| **Final** | `verified_roof_area_sqft` (from the survey visit, or confirmed by staff on the call) | "Final" | The quote builder |

- The quote builder **cannot send a quote** until roof area is verified and a sanctioned load is known, either confirmed from the bill or entered by staff from the DISCOM record. Error codes: `ROOF_NOT_VERIFIED`, `SANCTIONED_LOAD_UNKNOWN`.
- If the final size is lower than the provisional one, the reason is shown (e.g. "Roof fits 2 kW").

### Quote options must respect both constraints

```
max_allowed_kw = min(kw_by_roof(verified roof), sanctioned_load_kw, largest capacity option)
candidates     = { final_recommended_kw + offset  for offset in quote_option_offsets }   # [-1, 0, +1]
options        = sorted({ c ∈ capacity_options : smallest option ≤ c ≤ max_allowed_kw })
```

- An option that exceeds the verified roof capacity or the sanctioned load is **never offered**. The builder lists which candidates were removed and why (e.g. "4 kW removed: sanctioned load is 3 kW").
- If the *recommended* size itself exceeds the sanctioned load, it stays visible with the `exceeds_sanctioned_load` flag. It is **not** silently capped, but it is not offered as a quote option. Sales sees the options that fit the load and can add a note (for example, that the customer will apply for a load increase). That case is handled outside the system and is out of scope.
- If no option fits (e.g. roof < 100 sq ft), the builder shows "No system fits the verified roof" and the quote cannot be sent.

### 8.1 Sample leads (brief data only; missing inputs are not invented)

| | **Prashant Wankhede** (LD-30881) | **Rohit Meshram** (LD-30902) | **Ayesha Siddiqui** (LD-30915) |
|---|---|---|---|
| Ownership | Owner | Tenant | Owner |
| Monthly bill | ₹3,200 | ₹1,900 | ₹650 |
| Avg units/month | 340 | 210 | 85 |
| Annual units | 340 × 12 = **4,080** | 210 × 12 = 2,520 | 85 × 12 = **1,020** |
| Required kW | 4,080 ÷ 1,400 = **2.914…** | 2,520 ÷ 1,400 = 1.8 (computed, not used) | 1,020 ÷ 1,400 = **0.728…** |
| kW by usage | ceil → **3 kW** | — | ceil → **1 kW** |
| Roof area | **missing** → roof check *not verified* | missing | **missing** → *not verified* |
| Sanctioned load | **missing** → *verify* | missing | **missing** → *verify* |
| Tariff category | **missing** | missing | **missing** |
| **Recommendation** | **3 kW, provisional** (consumption only) ✓ matches brief | **None** ✓ (brief: –) | **1 kW, provisional** (consumption only) ✓ matches brief |
| Final recommendation | Needs verified roof ≥ 300 sq ft (and sanctioned load ≥ 3 kW to be quotable) | n/a | Needs verified roof ≥ 100 sq ft (and sanctioned load ≥ 1 kW) |
| Bill vs ₹1,000 | 3,200 ≥ 1,000 | 1,900 ≥ 1,000 | 650 < 1,000 |
| Reasons | none | `tenant` | `bill_below_threshold` |
| **Score / next action** | **High → survey visit** ✓ | **Low → call** ✓ | **Low → call** ✓ |

All three reproduce the brief's table **as provisional, consumption-based recommendations**. Because the brief gives no roof area for any sample lead, the roof constraint cannot be applied, so neither 3 kW nor 1 kW is final. These are the first unit tests (`test_sample_leads.py`), run on the brief's fields only, and they assert `status == "provisional"`.

For the **seed database**, the form makes roof area, roof type, pincode and consumer number mandatory, so the seeded leads need values for them. They are added as **clearly marked synthetic seed values** (`seed_note: "synthetic, not from brief"`) and are never used in the validation table above **[Q-3]**.

---

## 9. Pricing and subsidy

### 9.1 Pricing

```
price_rule = price_rules where min_kw ≤ kw ≤ max_kw AND effective_from ≤ priced_on ≤ coalesce(effective_to, ∞)
             none found → error PRICE_RULE_MISSING (quote cannot be sent)
gross_cost = kw × price_per_kw                → ROUND_HALF_UP to ₹1
```

Seed rule: 1–10 kW at **₹60,000/kW** **[A-3]**, GST-inclusive **[A-11]**, effective from 2026-01-01, open-ended.

Sanity check against the brief: the brief's "₹2 lakh order value" ≈ 3 kW × ₹60,000 = ₹1.8 lakh. That's the right order of magnitude, but it is still a placeholder.

### 9.2 Subsidy

```
rule = subsidy_rules where scheme_code = 'CENTRAL_RESIDENTIAL' AND segment = lead.segment
                      AND effective_from ≤ priced_on ≤ coalesce(effective_to, ∞)
lead not eligible (segment ≠ residential)      → subsidy = 0, status NOT_ELIGIBLE (explicit, shown with reason)
eligible but no rule for priced_on             → error SUBSIDY_RULE_MISSING (quote blocked; banner links to Rules)
expired rule (effective_to < priced_on)        → not selected → same error. Never silently reused.

raw     = Σ over slabs: max(0, min(kw, to_kw) − from_kw) × amount_per_kw     (linear pro-rata [A-5])
subsidy = min(raw, cap_amount)                 → ROUND_HALF_UP to ₹1
net     = gross − subsidy                      (if ≤ 0 → net = 0 and flag; never negative)
```

Seed rule **[CLIENT, illustrative]**: slabs `0–2 kW @ ₹30,000`, `2–3 kW @ ₹18,000`, cap ₹78,000, effective from 2024-02-13 (open-ended), with source note *"Client-stated figures. Verify amounts and eligibility against the current official scheme before launch."* **[A-4]**

| kW | Calculation | Raw | Cap applied? | **Subsidy** |
|---|---|---|---|---|
| 0.5 | 0.5 × 30,000 | 15,000 | no | **₹15,000** |
| 1 | 1 × 30,000 | 30,000 | no | **₹30,000** |
| 2 | 2 × 30,000 | 60,000 | no | **₹60,000** |
| 2.5 | 2 × 30,000 + 0.5 × 18,000 | 69,000 | no | **₹69,000** |
| 3 | 2 × 30,000 + 1 × 18,000 | 78,000 | at cap | **₹78,000** |
| 5 | 2 × 30,000 + 1 × 18,000 + 2 × 0 | 78,000 | at cap | **₹78,000** |

**Note on the cap:** with these slabs the maximum possible is 30 + 30 + 18 = ₹78,000, so the cap is never what actually limits the amount. To prove the cap logic works, the tests also use a **synthetic rule** (e.g. 0–10 kW @ ₹30,000, cap ₹78,000 → 5 kW = ₹78,000, raw ₹1,50,000).

**Fractional kW:** quotes use whole-kW options **[A-9]**. 0.5 and 2.5 kW exist to test the engine and for future non-integer options.

### 9.3 Effective-date tests

| Case | Setup | Expected |
|---|---|---|
| Boundary, start | Rule from 2026-04-01; priced_on 2026-04-01 | Rule applies (inclusive) |
| Boundary, end | Rule to 2026-12-31; priced_on 2026-12-31 | Applies; 2027-01-01 → next rule or error |
| Rule change | A to 2026-11-30, B from 2026-12-01 (different amounts) | Nov 30 → A, Dec 1 → B |
| Expired | Only A, ending 2026-06-30; priced_on 2026-11-02 | `SUBSIDY_RULE_MISSING` (not A, not 0) |
| Missing | No rules | `SUBSIDY_RULE_MISSING` |
| Overlap | Insert B overlapping A | Database rejects it (exclusion constraint); API returns 409 with a clear message |
| Not eligible | segment business | ₹0 with `NOT_ELIGIBLE` (distinct from missing) |

---

## 10. Savings and payback (estimates)

**Changes from Revision 1:** Revision 1 multiplied consumption by `bill ÷ units`, which included fixed charges that solar doesn't remove. That overstated savings and gave a payback of about 2.7 years for Prashant. The suggested "generation × self-consumption %" also needs one more limit: under net metering, generation above the household's own consumption is not worth the retail rate. Without a cap at annual consumption, an oversized system would appear to save more than the customer's entire energy bill.

### Formula

```
annual_generation   = kw × G                                                 (kWh, integer)
usable_generation   = min(annual_generation × U, annual_units)               (kWh)
    U = usable_generation_pct, initial 0.90  [A-6]   (losses, downtime, exports settled below retail)
    surplus above annual consumption valued at ₹0  [A-7]  (conservative)
fixed_charge        = confirmed fixed_charge from bill ?? default_fixed_charge_monthly (₹150 [A-8])
savings_rate        = (monthly_bill − fixed_charge) ÷ avg_monthly_units      (₹/kWh, variable part only)
annual_savings      = usable_generation × savings_rate                       → ROUND_HALF_UP ₹1
payback_years       = net_cost ÷ annual_savings                              → ROUND_HALF_UP 0.1
```

Built-in sanity property: when usable generation ≥ consumption, `annual_savings = (bill − fixed) × 12`. The estimate can never exceed the variable part of the customer's current bill.

**Sales overrides** (stored in the snapshot with the user and reason): `U`, `fixed_charge`, `savings_rate`.

**Safety rules:**

| Condition | Result |
|---|---|
| Units or bill missing | Savings and payback **"Not available: needs bill units"**. No number shown. |
| `savings_rate ≤ 0` (fixed ≥ bill) | "Not available: savings rate could not be estimated" |
| `annual_savings ≤ 0` | Payback "Not available" (never divide by zero or show a negative) |
| `net_cost = 0` | Payback "Immediate" with a note |
| Always | Labelled **"Estimate. Actual savings depend on usage, tariff changes and weather. Not guaranteed."** |

Known simplifications, documented: no panel degradation, no tariff escalation, average (not slab-marginal) tariff rate **[A-13]**. MSEDCL-style tariffs are tiered, so the marginal rate is usually higher than the average, which makes this estimate lean conservative.

### 10.1 Sample quotes

*Uses the brief's bill and units, plus placeholder assumptions A-3, A-6 and A-8. Illustrative only, not customer-specific savings. Sizes are the **provisional** 3 kW and 1 kW. A real quote would only be sent after roof and sanctioned load are verified (§8).*

| | Prashant, 3 kW | Ayesha, 1 kW | Rohit |
|---|---|---|---|
| Gross | 3 × 60,000 = **₹1,80,000** | 1 × 60,000 = **₹60,000** | No quote (tenant) |
| Subsidy | **₹78,000** | **₹30,000** | — |
| Net | **₹1,02,000** | **₹30,000** | — |
| Generation | 3 × 1,400 = 4,200 kWh | 1 × 1,400 = 1,400 kWh | — |
| Usable | min(4,200 × 0.9 = 3,780, 4,080) = **3,780** | min(1,260, 1,020) = **1,020** | — |
| Savings rate | (3,200 − 150) ÷ 340 = ₹8.9706/kWh | (650 − 150) ÷ 85 = ₹5.8824/kWh | — |
| Annual savings | 3,780 × 8.9706 = **₹33,909** | 1,020 × 5.8824 = **₹6,000** | — |
| Payback | 1,02,000 ÷ 33,909 = **≈ 3.0 years** | 30,000 ÷ 6,000 = **5.0 years** | — |

Prashant's three options (offsets −1/0/+1), showing why the recommended size matters:

| Option | Gross | Subsidy | Net | Usable kWh | Savings | Payback |
|---|---|---|---|---|---|---|
| 2 kW | ₹1,20,000 | ₹60,000 | ₹60,000 | 2,520 | ₹22,606 | ≈ 2.7 y |
| **3 kW** | ₹1,80,000 | ₹78,000 | ₹1,02,000 | 3,780 | ₹33,909 | ≈ 3.0 y |
| 4 kW | ₹2,40,000 | ₹78,000 | ₹1,62,000 | 4,080 (capped by usage) | ₹36,600 | ≈ 4.4 y |

This table shows every *candidate* before the constraints in §8 are applied. With real verified data, options are filtered:

| Verified roof | Sanctioned load | Options actually offered |
|---|---|---|
| 450 sq ft | 5 kW | 2, 3, 4 kW |
| 450 sq ft | 3 kW | 2, 3 kW (4 kW removed: load) |
| 250 sq ft | 5 kW | 1, 2 kW. Final recommendation becomes 2 kW (roof), so candidates are 1, 2, 3, and 3 is removed (roof) |
| 80 sq ft | any | none: "No system fits the verified roof" |

**Why the payback figures still look short:** the placeholder price and fixed charge are not client data. With real installer prices the numbers will change. This is listed in the TDD as a limitation, not hidden.

---

## 11. Immutable quotation snapshot

A quote is created once, at *Send*, with:

```json
{
  "calc_version": "calc-1.0.0",
  "priced_on": "2026-11-02",
  "inputs": {"ownership":"owner","segment":"residential","roof_area_sqft":…, "avg_monthly_units":340,
             "monthly_bill":3200, "fixed_charge":{"value":150,"source":"default_setting"},
             "sanctioned_load_kw":…, "bill_reading_id":"…"},
  "settings": {"generation_kwh_per_kw_year":1400, "roof_sqft_per_kw":100, "usable_generation_pct":0.9, …},
  "price_rule":   {"id":"…","price_per_kw":60000,"gst_inclusive":true,"effective_from":"2026-01-01","effective_to":null},
  "subsidy_rule": {"id":"…","scheme_code":"CENTRAL_RESIDENTIAL","slabs":[…],"cap_amount":78000,
                   "effective_from":"2024-02-13","effective_to":null,"source_note":"…"},
  "overrides": [{"field":"fixed_charge","from":150,"to":180,"by":"user-id","reason":"…"}],
  "assumptions": ["A-3","A-4","A-6","A-7","A-8","A-11","A-13"],
  "options": [{"kw":2,…},{"kw":3,…,"recommended":true},{"kw":4,…,"flags":["roof_unverified"]}],
  "results_for_selected": {…}
}
```

- The rule **rows are copied in**, not just their ids, so a deleted or edited rule cannot change history.
- **What is immutable:** the snapshot and the quote's identity and commercial columns (number, lead, priced_on, calc_version, created_by, sent_at). The `quotes_guard` trigger rejects any change to them.
- **What can change:** lifecycle metadata only (`status`, `selected_kw`, `accepted_at`, `accepted_by`, `superseded_at`, `superseded_by_quote_id`), only through the transitions in §3.8, and each field only once.
- Revising a quote means inserting a new one and marking the old one `superseded` in the same transaction. Old quotes are never edited.
- The snapshot also records the roof and sanctioned-load values used and the candidates that were removed (§8), so a reviewer can see why an option was or wasn't offered.
- The **PDF is rendered from the snapshot on demand**, so it is always reproducible and nothing extra needs storing.
- Integration test: send a quote → edit the price and subsidy rules → the quote API and PDF still show the old numbers.

---

## 12. Project lifecycle

| # | Stage | Set by | Notes |
|---|---|---|---|
| 1 | Advance received | Sales records the advance (amount + `SIMULATED-` reference) | Creates the project and the status token |
| 2 | Installation scheduled | Sales | optional date |
| 3 | Installation completed | Sales | |
| 4 | Net metering completed **[Q-6]** | Sales | DISCOM net-meter step; recommended because the brief names it |
| 5 | Subsidy application submitted | Sales | Portal filing itself is out of scope **[CLIENT]** |
| 6 | Subsidy credited | Sales | Terminal |

- Transitions only go forward by one step. A backward correction requires a reason and is logged.
- Each change writes a `project_events` row (who, when, from, to, note) and a simulated notification.
- **Days in stage** is shown in the Projects table and sortable. The full "stuck projects" dashboard is optional depth.

### Status link

- `token = secrets.token_urlsafe(32)`. Only `sha256(token)` is stored, and the token is shown once to copy (regenerate if lost).
- URL: `/s/{token}`, served with `noindex`, `Referrer-Policy: no-referrer` and rate limiting.
- **Revoke** sets `revoked_at`; the link then returns a neutral "This link is no longer active" page. **Regenerate** revokes the old token and issues a new one.
- Public response is limited to the homeowner's first name, the project code, the stage list with completion dates and the current stage.

---

## 13. Notifications (simulated)

- Triggers: quote sent, project created (with status link), every stage change.
- `notify.send()` writes to `notifications` with `delivery_status = "simulated"`. There is no external call.
- Templates exist in **English, Hindi and Marathi**. The homeowner's `preferred_locale` picks the template, and the status link in the message carries the same locale.
- The UI shows a grey **"Simulated, not sent"** badge on every notification in Screen 8. The homeowner dashboard shows "Updates would be sent to your WhatsApp (demo)".
- Recipient phone numbers are masked in the UI and in storage display.

---

## 14. Security and privacy

| Area | Measure |
|---|---|
| Secrets | `.env` git-ignored; `.env.example` lists names only; keys only on Render; frontend env holds only `BACKEND_URL` (server-side) |
| Passwords | argon2id; generic "incorrect details" errors; login rate limit |
| Sessions | httpOnly Secure cookie, 8 h expiry, logout clears it, custom-header CSRF check |
| Authorisation | Role dependencies plus object-level filters; 404 for foreign records |
| Input validation | Pydantic on every request (enums, ranges, regex); zod on the client for UX only |
| Uploads | Size cap, magic-byte check, decode verification, pixel cap, re-encoding (EXIF/GPS removed), encrypted/corrupt PDF rejection, page limits |
| File access | No public URLs; authenticated, object-checked endpoints; `no-store` |
| Personal data (DPDP Act 2023 **[CLIENT]**) | Purpose-specific consent with version and timestamp; consumer numbers masked in lists (`••••4821`); status page shows no personal data; no personal data in logs (only ids); no analytics or third-party scripts. **We do not claim legal compliance.** |
| Transport and headers | HTTPS (Vercel/Render); CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (`no-referrer` on `/s/*`) |
| CORS | Backend allows only `FRONTEND_ORIGIN` (normal traffic is same-origin through the rewrite) |
| AI data minimisation | Only 1–2 relevant pages or the image are sent to providers; nothing is cached across users |

Next steps documented, not built: data deletion/export on request, a retention schedule for bill files **[Q-12]**, refresh-token rotation, a shared rate-limit store.

---

## 15. Testing strategy

### 15.1 Unit tests: calculation engine (pure, no database)

| Area | Cases |
|---|---|
| Annual consumption | 340 → 4,080; 0 → 0; missing → error `USAGE_UNKNOWN`; negative → validation error |
| Sizing | samples (3 provisional, –, 1 provisional); exactly 350/mo → 3 kW (not 4); 351/mo → 4 kW; above the largest option → largest option and flag; final size uses verified roof |
| Quote options | the four rows in §10.1 (roof/load filtering); recommended above load → flagged, not offered; no fitting option → `NO_OPTION_FITS`; roof unverified → `ROOF_NOT_VERIFIED` |
| Quote lifecycle | sent → accepted; sent → superseded on new quote; accepted is terminal; change to an immutable column rejected by the trigger; `selected_kw` outside the snapshot options rejected; second open quote per lead rejected |
| Roof capacity | 250 sq ft → 2 kW; 99 → 0 → `roof_too_small`; roof limits usage (need 3, roof 2 → 2) |
| Scoring | samples (High, Low tenant, Low small bill); threshold boundary 999/1,000/1,001; confirmed bill used over declared; override is stored |
| Pricing | 3 × 60,000; missing rule → error; kW outside rule range → error |
| Subsidy | 0.5/1/2/2.5/3/5 kW table; synthetic cap rule; not eligible → 0 with status |
| Effective dates | All rows in §9.3 |
| Generation | kW × 1,400; edited factor (e.g. 1,350) used and snapshotted |
| Savings | Prashant/Ayesha examples; usable capped at consumption; extracted fixed charge preferred over default; overrides applied |
| Payback | ≈ 3.0 and 5.0; savings ≤ 0 → not available; net 0 → immediate; rounding 2.95 → 3.0 |
| Rounding | ROUND_HALF_UP at outputs only; no float anywhere (a type check test) |

Each test file includes, in its docstring, the formula, inputs, expected output and assumption ids. The TDD's calculation appendix is generated from these.

### 15.2 Upload tests (generated synthetic fixtures)
Valid JPG/PNG/WebP · EXIF GPS removed after re-encoding · text-based PDF → text path chosen and fields parsed · scanned PDF → pages rendered → vision path · multi-page PDF → only relevant pages sent · corrupted PDF → 422 · password-protected PDF → 422 with message · 10 MB + 1 byte → 413 · `.exe` renamed `.jpg` → 415 · blurry, dark and tiny images → `needs_reupload` with a reason · same file twice → no second AI call.

### 15.3 Integration tests (pytest + real Postgres in CI)
RBAC matrix (§4) · homeowner A cannot read B's lead, bill, quote or project (404) · homeowner cannot call staff endpoints (403) · AI fallback: Groq 429 → Gemini OK; Groq bad JSON → Gemini; both fail → `failed_manual` and the lead persists · quote snapshot immutability (rule edit, then compare; direct UPDATE blocked by trigger) · subsidy rule update affects only new quotes · overlapping rule → 409 · status link: valid → limited fields only; revoked → inactive; regenerated → old one dead · public status response contains no personal-data keys (asserted).

### 15.4 End-to-end (Playwright, `AI_MODE=test`)
Homeowner signs up through the lead form → uploads a synthetic bill → extraction → confirms → sales signs in, sees the High lead → enters survey → sends quote → homeowner views and accepts → sales records advance → project created → sales advances a stage → the public status page shows the new stage.

---

## 16. Deployment

| Part | Platform | Notes |
|---|---|---|
| Frontend | Vercel | `BACKEND_URL` used in `next.config` rewrites; security headers in config |
| Backend | Render web service (Python) | Build: `pip install -r requirements.txt`. Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Database | Neon | First migration runs `CREATE EXTENSION IF NOT EXISTS citext` and `… btree_gist`; seed with `python -m seed` (idempotent) |

**Environment variable names**
- Backend: `DATABASE_URL`, `JWT_SECRET`, `JWT_TTL_HOURS`, `FRONTEND_ORIGIN`, `COOKIE_SECURE`, `AI_MODE`, `GROQ_API_KEY`, `GROQ_VISION_MODEL`, `GROQ_TEXT_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `AI_TIMEOUT_SECONDS`, `MAX_UPLOAD_MB`, `SEED_DEMO_PASSWORD`
- Frontend: `BACKEND_URL`

**Cold starts:** Render's free tier sleeps after ~15 minutes idle, and the first request takes ~30–60 s. The frontend pings `/api/health` on load and shows a "Waking up the server…" state. Paying for Render Starter during the review removes this.

**Free-tier limits** (to be verified at deploy time): Neon storage cap, Render sleep and monthly hours, Groq/Gemini rate limits, and Vercel's limits on proxied request size and duration **[Q-9]**.

**Local development:** Docker Compose for Postgres only. Backend runs with `uvicorn --reload`, frontend with `next dev`. Full steps go in `deployment.md`.

---

## 17. Assumptions register

| ID | Assumption | Initial value | Why needed | Configurable | Client to confirm |
|---|---|---|---|---|---|
| A-1 | Minimum monthly bill for a survey visit | ₹1,000 | Client wants to filter "₹600 bills" but gave no threshold | Yes (settings) | **Yes** |
| A-2 | Roof area per kW | 100 sq ft | Roof capacity check | Yes | **Yes** |
| A-3 | Installation price | ₹60,000/kW, 1–10 kW | No prices given | Yes (dated `price_rules`) | **Yes** |
| A-4 | Subsidy structure | ₹30k/kW to 2 kW, ₹18k for the 3rd, cap ₹78k | Given by the client as illustrative; must be verified | Yes (dated `subsidy_rules`) | **Yes, verify official** |
| A-5 | Pro-rata subsidy for fractional kW | Linear within each slab | Brief is silent | Engine logic | Yes |
| A-6 | Usable generation share | 90% | Losses, downtime, exports below retail | Yes, plus sales override | **Yes** |
| A-7 | Value of surplus above consumption | ₹0 | Net-metering settlement rate unknown | No (documented) | Yes |
| A-8 | Default fixed charge when not on the bill | ₹150/month | Fixed charges aren't saved by solar | Yes, plus sales override, plus AI extraction | **Yes** |
| A-9 | System capacity options | Whole kW, 1–10 | Sizing and quote options | Yes | Yes |
| A-10 | Options shown in a quote | recommended −1, 0, +1 within limits | "System options" in the brief | Yes | No |
| A-11 | Tax treatment | Prices are GST-inclusive; no separate GST line | Brief is silent | Flag on the price rule | **Yes** |
| A-12 | Bill file storage | Postgres bytea; S3/R2 later | Free tier, no public URLs | No | No |
| A-13 | Savings model simplifications | No degradation, no escalation, average rate | Simple, explainable estimate | No (documented) | No |
| A-14 | Roof types | RCC flat, metal sheet, tiled, other | Form needs options | Code enum | Yes |
| A-15 | Extra Low-score reasons | Roof < 1 kW, usage unknown | Brief names only tenant and small bill | Yes (toggle) | Yes |
| A-16 | Photo quality thresholds | 700 px short side (receipt shape h ≥ 2.2 w: 320 px short, 900 px long), brightness 40–235, edge variance measured without enlarging | Re-upload trigger; narrow thermal receipts are readable | Yes (env/settings) | No |
| A-17 | HEIC not accepted | — | iOS converts to JPEG for web | No | No |
| A-18 | Consumer number format check | Digits only, 9–15 (soft flag) | Exact DISCOM format not given | Yes | Yes |
| A-19 | Subsidy eligibility | Residential segment only | Brief says "central residential scheme" | Yes (rule segment) | **Yes** |
| A-20 | Rule date | Date the quote is generated (`priced_on`) | Brief is silent | No | Yes |
| A-21 | Advance payment | Amount entered by sales; payment simulated | Advance amount not given | — | Yes |
| A-22 | Project stages | 6 stages in §12 | Brief names advance → subsidy credited only | Enum | **Yes** |
| A-23 | Bill format | MSEDCL-style layouts; synthetic samples, no real branding or data | Vidarbha DISCOM context | — | Yes (real sample bills) |
| A-24 | Session lifetime | 8 h | Security vs convenience | Env | No |
| A-25 | Average-units method | Mean of ≥ 3 months of history, else current month | Bills vary by month | No | No |
| A-26 | Hindi and Marathi wording | Drafted by the developer with AI help | No client-supplied translations | Message files | **Yes, native review before launch** |
| A-27 | Number format in hi/mr | Western digits, Indian grouping | Consistency with bills and payments | next-intl config | Yes |
| A-28 | Staff UI language | English only | Brief's language constraint concerns customers | — | Yes |
| A-29 | Roof verification before quoting | Survey or staff call confirmation required | Final size must reflect real roof capacity | No | Yes |
| A-30 | Multi-month bills | A bill covering 25–35 days counts as one month; otherwise units, bill and fixed charge × (365/12) ÷ days | Spot bills often cover 2–3 months | No | Yes |

---

## 18. Sample-lead numerical summary

See §8.1 (sizing and score), §9.2 (subsidy table) and §10.1 (quotes). Summary:

| Lead | Annual units | Recommended | Score | Gross | Subsidy | Net | Payback (illustrative) |
|---|---|---|---|---|---|---|---|
| Prashant | 4,080 | 3 kW **provisional** | High → visit | ₹1,80,000 | ₹78,000 | ₹1,02,000 | ≈ 3.0 y |
| Rohit | 2,520 | none | Low (tenant) → call | — | — | — | — |
| Ayesha | 1,020 | 1 kW **provisional** | Low (bill < ₹1,000) → call | ₹60,000 | ₹30,000 | ₹30,000 | 5.0 y |

Provisional means consumption-based only. The final size, and which options are offered, depend on the verified roof area and sanctioned load (§8).

**Missing from the brief for all three:** roof area, roof type, pincode, consumer number, tariff category, sanctioned load, fixed charge.

---

## 19. Open questions and contradictions

| ID | Issue | Proposed handling |
|---|---|---|
| Q-1 | The brief says "AI: bill reading **and lead score**", but the score is deterministic. | The AI supplies the *verified inputs*; the score is rules on top. Justify in the TDD: explainable, auditable, consistent, and "never rejects" is guaranteed. |
| Q-2 | ~~English-first vs the brief's "Marathi and Hindi"~~ **Resolved in Rev 3.** | Hindi and Marathi are mandatory for the full homeowner journey (§2), built in M4–M6, with a key-parity CI check. |
| Q-3 | Sample leads lack roof area, pincode, roof type and bill details. | Validate on brief fields only; seed with labelled synthetic values. |
| Q-4 | The ₹78,000 cap is never what limits the amount with the given slabs. | Keep the cap (future rule changes); test it with a synthetic rule. |
| Q-5 | Small businesses are customers, but the lead form fields don't distinguish home vs business, which matters for subsidy eligibility. | Add one question "Home or business?" to step 1. |
| Q-6 | The revision's stage list omits net metering, which the brief mentions (DISCOM). | Add "Net metering completed" as stage 4. |
| Q-7 | Rules need an editor, but the brief has only two roles. | Add a seeded `admin` role (one account); sales can view rules. |
| Q-8 | Revision 2 adds an admin screen, so there are 9 screens vs "about 6–8". | Admin is "Must have / optional depth" in the brief; keep it deliberately simple. |
| Q-9 | 10 MB uploads and up to ~50 s AI chains through Vercel's proxy may hit platform limits. | The async poll design removes the duration risk. **M1 finding:** Next.js buffers proxied request bodies at 10 MB by default and drops the connection beyond that, even with `/api` excluded from `proxy.ts`. Fixed locally with `experimental.proxyClientMaxBodySize: "12mb"` (9 MB and 11 MB verified through the proxy). The Vercel production limit is still to be verified in M7. Fallback: the upload endpoint is called directly on the Render origin with a short-lived upload token (CORS restricted). |
| Q-10 | Neon free storage is limited. | Documented. Images are compressed client-side; production uses object storage. |
| Q-11 | "Same-day quote" is a success metric, but nothing measures it. | Optional: show "survey → quote time" on lead detail (cheap, from timestamps). |
| Q-12 | Bill retention period for personal data is unknown. | Documented as a next step; client to define. |
| Q-13 | Advance payment amount or percentage is unknown. | Sales enters the amount; simulated. |
| Q-14 | **Technical risk:** ReportLab draws Devanagari correctly only with text shaping (conjuncts and vowel signs). | In M5, spike ReportLab's HarfBuzz shaping support (`uharfbuzz`) with an embedded Noto Sans Devanagari font, and verify visually with real conjuncts (e.g. "क्षमता", "स्थापना"). If the output is not correct, the fallback keeps the approved stack: headings and labels as pre-shaped text, and the result reported honestly. Hindi/Marathi PDFs are not shipped looking broken. |

---

## 20. Design system

| Token | Value |
|---|---|
| Background | `#FFFFFF`; surface pale teal-grey `#F2F6F5`; border `#DCE4E2` |
| Ink | `#18211F` primary text, `#4F5D5A` secondary |
| Brand teal (from the client logo) | `#006863` for primary actions, links, savings figures and the focus ring. Contrast on white is 6.64:1 (AA for text). Deep teal `#004A46` and wash `#E3EFED` for active states. |
| Brand gold (from the client logo) | `#E5B257`, **decorative only**: the sun mark and the horizon line. Contrast on white is 1.94:1, so it is never used for text on white. |
| Attention (amber) | `#B45309` text on `#FEF3C7`, **only** for Low score, flags and stuck projects |
| Error | `#B91C1C`, used only for errors |
| Night teal | `#012E2B` for dusk sections: the landing hero, sign-in art panel, staff sidebar and footer. White text 13.9:1; gold button on night 8.1:1; soft gold `#F6DFA8` only for small accent text on night. |
| Type | Two Indian families drawn for both Latin and Devanagari, so English, Hindi and Marathi share one voice: **Anek Devanagari** (variable width, set semi-expanded) for display headings, and **Mukta** for reading text. `tabular-nums` for money. Devanagari text gets line height 1.7 (headings 1.35) so vowel signs don't clip. Layouts are tested with the longest of the three translations. |
| Illustrations | Custom inline SVGs in the brand palette, a different one per page: **landing**, a Vidarbha rooftop at sunrise (flat RCC roof, water tank on the stair room, tilted panels, neem tree, Sankranti kite, ray fan echoing the logo); **sign-in**, sun → panel → home joined by one animated gold "flow" line (the only motion; reduced-motion respected); **steps and empty states**, small line spots. The client's sun mark is used only as the logo. |
| Product name | **HelioFlow**, one word, everywhere. |
| Shape | 8 px radius on inputs, 12 px on cards; 1 px borders; one subtle shadow for overlays only; no gradients or decorative motion |
| Spacing | 4 px grid; homeowner column `max-w-md`; staff content `max-w-7xl` |
| Currency | `Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:0})` → ₹1,02,000 |

**Patterns**
- Homeowner flow: one question group per step, a sticky bottom primary button on phones, 44 px tap targets.
- Staff: sidebar on desktop, top bar with a menu sheet on phones; tables become cards below 768 px.
- Every async view has a skeleton, an empty state with one clear action, an error state with retry, and a success toast (sonner).
- Bill reading progress shows **real** steps from the polled status: *Checking file → Reading bill → Ready to confirm*.
- The quote hero is three stacked figures (size, cost after subsidy, payback "estimate"), then *See how we calculated this* (expandable breakdown and assumptions). The PDF has the same order, colours and wordmark ("HelioFlow"), with an assumptions and disclaimer footer.
- Accessibility: WCAG AA contrast, visible focus, labelled inputs, error text linked with `aria-describedby`.

---

## 21. Milestones

Each milestone ends with: what was built, files changed, **actual** test output, known issues, a suggested commit message (no trailers), and a stop for review. Claude never runs `git commit` or `git push`.

| # | Milestone | Done when (verified, not assumed) |
|---|---|---|
| M1 | Repo skeleton (frontend + backend), Docker Compose Postgres, Alembic baseline with `citext` + `btree_gist`, all tables and constraints (including unique `bill_file_id` and `quotes_guard`), auth (sign-up, sign-in, sign-out, me), RBAC dependencies, next-intl routing with en/hi/mr and the switcher, seed (staff, admin, 3 sample leads, rules), CI workflow, proxy upload-size probe (Q-9) | `pytest` green for auth/RBAC; migrations apply on a clean database; constraint tests pass; sign-in works through the Next.js proxy locally in all three locales |
| M2 | Calculation engine: sizing, scoring, pricing, subsidy, generation, savings, payback, rule selection | All §15.1 tests pass, including the three sample leads and the subsidy table; coverage ≥ 95% for `services/calc` |
| M3 | Upload gate, PDF routing, quality gate, Groq → Gemini → manual chain, polling API, confirmation API, demo/test modes | All §15.2 tests and the fallback integration tests pass; one **real** Groq extraction on a synthetic bill verified manually and reported honestly |
| M4 | Homeowner screens 1–3 **in en/hi/mr**, scoring on confirmation (provisional size), empty/loading/error states, translated error codes | Manual phone-width run-through in all three languages; Playwright smoke test for the lead form in Hindi; key-parity check green |
| M5 | Staff screens 6–7, roof/load verification, constraint-filtered quote options, quote builder with overrides, snapshot + lifecycle transitions, ReportLab PDF (en/hi/mr, Q-14 spike), homeowner screen 4 in all three languages | Snapshot immutability and transition tests pass; options-filter tests pass; PDFs checked visually in each language and reported honestly |
| M6 | Projects (screen 8), stage transitions and events, status link (screen 5, en/hi/mr), simulated notifications in the homeowner's language, admin rules screen (9) | Status-link and revocation tests pass; overlap 409 shown in the UI |
| M7 | UI polish, full E2E, deploy (Vercel + Render + Neon), `deployment.md`, TDD | E2E passes in CI; live URL checked from a phone; demo logins work |

**Before the first commit (end of M1)**, Amit verifies `git config user.name` and `git config user.email`.
