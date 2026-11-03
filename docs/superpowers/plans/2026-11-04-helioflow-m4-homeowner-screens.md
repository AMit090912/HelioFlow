# HelioFlow M4 — Homeowner Screens and Lead Qualification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A homeowner can go from the landing page to a qualified lead entirely on a phone, in English, हिन्दी or मराठी. They answer a few questions, create an account with consent, upload a bill, check and confirm what the AI read, and see their next step. The lead is scored and sized (provisionally) as soon as the bill is confirmed.

**Architecture:**
- Backend:
  - `app/api/leads.py`: create a lead, list my leads, lead detail.
  - `app/services/qualification.py`: score and size on confirmation, using the M2 engine with DB-loaded settings.
  - `PATCH /api/auth/me`: save the preferred locale.
- Frontend: three routes, `/[locale]/get-solar` (3-step form), `/[locale]/my/bill/[id]` (check your bill) and `/[locale]/my` (dashboard). They are built from small client components, TanStack Query and react-hook-form + zod. Errors come from the API as codes and are translated in `messages/*.json`.

**Spec:** `docs/ARCHITECTURE.md` §2 (screens 1–3, languages, journeys, lead status machine), §7 (scoring), §8 (provisional vs final), §6.4 (human verification), §14 (consent, DPDP), §20 (design).

## Global Constraints
- **The homeowner never sees the score label** (§2). Homeowner APIs leave out `score` and `score_reasons`; they return only `next_action` and the provisional size.
- **Consent is required before a lead exists** (`consent_at`, `consent_version = "2026-11-v1"`).
- **Every homeowner-facing string exists in en, hi and mr.** `npm run check:i18n` must pass, and every API error code shown to a homeowner has a translation.
- **Scoring runs only on confirmed bill values** (`bill_source = "confirmed"`). Sizing is provisional and based on the declared roof area. Score reasons store plain numbers (`"650"`, not `"650.00"`).
- **Lead status moves forward only:** `draft → bill_processing → bill_review → (survey_pending | call_pending)`. Confirming a bill moves the lead to the qualified next step.
- **Design:** the M1 redesign language applies (night-teal brand moments, Anek display type, Mukta body, gold only as decoration, one illustration per screen). Phones come first, with 44 px tap targets.
- Claude commits locally at the end of the milestone with plain-English messages and never pushes.

## Review Focus
1. **Reloading mid-form keeps step-1 answers** (sessionStorage) and never re-creates a lead.
2. **An already signed-in homeowner skips the account step.** A signed-in staff user is sent to their inbox, not the form.
3. **A slow AI read keeps the check-bill screen in an honest "reading" state** with real progress. It falls back to manual entry if the reading fails, and never loops forever.
4. **Editing a value on the check-bill screen and confirming** sends exactly the values on screen, so the AI's suggestions can't silently override the homeowner's edits.
5. **A tenant or a small-bill lead sees a respectful "we'll call you" next step**, never "Low" or "rejected".

---

### Task 1: Lead API and qualification (backend, test-first)
**Files:** `app/schemas/leads.py`, `app/api/leads.py`, `app/services/qualification.py`, `app/api/bills.py` (call qualification after confirm), `app/api/auth.py` (PATCH /me), `app/main.py`; tests `tests/integration/test_leads_api.py`, `tests/integration/test_qualification.py`.

**Produces:**
- `POST /api/leads`, homeowner only, body `LeadIn{ownership, property_type, roof_type, roof_area_sqft 1..100000, monthly_bill 1..1000000, pincode ^[1-9]\d{5}$, consent: true}` → 201 `LeadMine`. `consent != true` gives 422 `CONSENT_REQUIRED`. The code is `LD-` plus 6 digits, unique.
- `GET /api/leads/mine` → `[LeadMine]`, newest first.
- `GET /api/leads/{id}` → `LeadMine` for the owner (404 otherwise).
- `LeadMine` fields: `id, code, status, ownership, property_type, roof_type, roof_area_sqft, declared_monthly_bill, pincode, next_action, recommended_kw, recommendation_status, current_reading{id,status}|null, latest_reading{id,status}|null, created_at`. It has no score or reasons.
- `qualify_lead(db, lead, reading) -> None`: sizes with `recommend()` (declared roof, the reading's sanctioned load and confirmed average units), scores with `score_lead(…, bill_source="confirmed")`, then sets `score, score_reasons (plain), recommended_kw, sizing_detail, next_action`. Status becomes `survey_pending` or `call_pending`. It is called inside the confirm transaction.
- `PATCH /api/auth/me {preferred_locale}` → `UserOut`.
- [ ] **Tests (RED → GREEN):**
  - Create: validation, consent, staff gets 403, code format.
  - Mine: only my leads, newest first, no score field.
  - Confirm qualifies each sample lead correctly: Prashant High/visit/3 kW provisional, Rohit tenant call/no size, Ayesha small-bill call/1 kW.
  - A zero-units bill gives a call.
  - Reasons are stored as plain numbers.
  - The PATCH locale persists.

### Task 2: Frontend data layer and translations
**Files:** `frontend/lib/leads.ts` (typed API calls and query hooks), `frontend/lib/format.ts` (₹ Indian grouping, kW), `frontend/messages/{en,hi,mr}.json` (form, bill check, dashboard, all new error codes).
- [ ] `check:i18n` passes, and every error code the bills/leads APIs can return is present in all three languages.

### Task 3: Screen 1, the 3-step lead form `/[locale]/get-solar`
**Files:** `app/[locale]/get-solar/page.tsx`, `components/lead-form/{stepper,step-home,step-account,step-bill,choice-card}.tsx`, a new `SpotUpload` illustration.
- **Step 1, home:** owner/tenant, home/business and roof type as large choice cards; roof area and monthly bill as numeric inputs with units; pincode. Saved to sessionStorage.
- **Step 2, account:** name, mobile, optional email, password and the consent checkbox. Skipped if already signed in as a homeowner. "Already have an account? Sign in" returns to the form. This step creates the lead.
- **Step 3, bill:** drag/drop or tap-to-pick (camera on phones), client-side compression for images, clear size and type errors, upload progress, then a redirect to the check-bill screen.
- The landing CTA and the sign-in page's "New here?" point here. Staff are redirected to the inbox.

### Task 4: Screen 2, check your bill `/[locale]/my/bill/[id]`
**Files:** `app/[locale]/(homeowner)/my/bill/[id]/page.tsx`, `components/bill-check/{reading-progress,bill-preview,values-form,reupload-panel}.tsx`.
- **Processing:** polls every 1.2 s and shows real steps, ending after the server's terminal state.
- **needs_review:** the preview image sits beside the editable values (stacked on phones). Low-confidence or flagged fields are highlighted with a plain-language note. "Confirm these values" sends the full form.
- **needs_reupload:** shows the specific reason (blurry, dark, too small, not a bill) and tips, with a re-upload control.
- **failed_manual:** an explanation plus the same form, empty, for typing values in.
- **confirmed:** goes to `/my`.
- The demo-mode banner shows when `is_demo` is true.

### Task 5: Screen 3, the dashboard `/[locale]/my`
- **No lead:** an empty state with a "Check if solar fits my home" CTA.
- **Lead in progress:** a "Continue: check your bill" card.
- **Qualified:** a next-step hero ("We'll schedule your survey visit" or "We'll call you first"), "about N kW (confirmed after the survey)", the bill summary, and a timeline of what happens next. The score label is never shown.

### Task 6: Verification
- [ ] Backend suite, ruff and alembic check.
- [ ] Frontend lint, typecheck, i18n and build.
- [ ] Playwright run against the dev servers (`AI_MODE=demo`, synthetic sample bill): full journey in Hindi at 390 px and in English on desktop; screenshots reviewed.
- [ ] Fresh reviewer, fix pass, then milestone commits.
