# HelioFlow M5: Staff Inbox, Quote Builder and Quotes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sales can work a lead end to end:
1. Find it in the inbox.
2. Check the bill (AI next to confirmed values).
3. Verify roof and sanctioned load.
4. Build a quote with live, constraint-filtered options and reasoned overrides.
5. Send it as an immutable snapshot.

The homeowner then sees the quote (screen 4) in en, hi or mr, downloads the PDF in their language and accepts one option.

**Architecture:**
- **Backend:** a `quotes` service wraps the existing pure engine (`build_quote_options`) and owns four jobs:
  - turning the result into a snapshot;
  - numbering;
  - supersede and accept transitions;
  - simulated notifications.
- **Staff API:** under `/api/staff/*`. Quote reads, accept and PDF live under `/api/quotes/*`.
- **Lead audit:** a new `lead_events` table records every staff action on a lead.
- **PDF:** ReportLab Platypus with HarfBuzz shaping (Q-14 spike passed, see below).
- **Frontend:** two English staff screens (inbox and lead detail with builder) and one translated homeowner screen (`/my/quote/[id]`), plus a quote card on the dashboard.

**Tech stack:**
- FastAPI, SQLAlchemy 2 and Alembic.
- ReportLab 5.1 with `uharfbuzz` (new dependency) and Mukta TTF (OFL, bundled).
- Next.js 16, next-intl, TanStack Query, react-hook-form and zod.

**Spec:** `docs/ARCHITECTURE.md`:
- §2 screens 4, 6 and 7; the sales journey; the lead status machine.
- §3.2 and §3.8 (quotes lifecycle and the `quotes_guard` trigger), §3.11.
- §4 (permission matrix), §8 (provisional vs final; options filter), §9, §10 (overrides, safety rules), §11 (snapshot), §19 Q-14, §20 (quote hero pattern).

**Q-14 spike result (2026-11-03):**
- With `uharfbuzz` installed, a `Paragraph` whose `ParagraphStyle` has `shaping=1` renders Mukta Devanagari correctly. Checked: क्षमता, वर्ष, अनुमानित, स्थापनेनंतर, द्ध, ह्म, प्रणाली, सब्सिडी, plus line wrapping.
- `canvas.drawString(..., shaping=True)` is still broken. **Draw all PDF text through Paragraphs only.**

## Global Constraints

- **Permission matrix (§4):**
  - Survey, verification, upgrade, close and quote building and sending are for `sales` and `admin` only.
  - View and accept quote: the owning homeowner. Sales and admin can view only.
  - A homeowner reading someone else's quote or PDF gets **404**.
- **Immutable quotes (§3.8, §11):**
  - The snapshot copies the rule **rows**, the settings values, the inputs, the overrides (field, from, to, by, reason), the removed candidates and the assumptions.
  - Quote views and PDFs are rendered **only from the snapshot**, never from current rules.
  - Revising means inserting a new quote and superseding the old one in the same transaction.
- **Send prerequisites (§8):**
  - `ROOF_NOT_VERIFIED` when there is no `verified_roof_area_sqft`.
  - `SANCTIONED_LOAD_UNKNOWN` when there is neither a staff-verified nor a bill-confirmed load.
  - `NO_OPTION_FITS`; `PRICE_RULE_MISSING` and `SUBSIDY_RULE_MISSING` from the engine; `NOT_QUOTABLE_TENANT`.
  - All of these are returned as 422 with the code.
- **Overrides (§10):** only `usable_generation_pct`, `fixed_charge_monthly` and `savings_rate`. Each needs a reason (min 5 chars) **to send**. Preview accepts them without a reason.
- **Lead status moves forward only.** The allowed staff moves:
  - `call_pending → survey_pending`: upgrade, reason required.
  - `survey_pending` or `call_pending` → `surveyed`: verification recorded.
  - `survey_pending`, `call_pending`, `surveyed` or `quoted` → `quoted`: on send.
  - `quoted → accepted`: homeowner accepts.
  - Any non-terminal status → `closed_lost`: reason required. Terminal statuses are `accepted`, `converted` and `closed_lost`.
- **Every staff action writes a `lead_events` row:** actor, from, to, note.
- **Money and kW:**
  - Rupees ROUND_HALF_UP to ₹1 and payback to 0.1 year, both from the engine.
  - The API sends decimals as plain strings ("102000", "3").
  - The UI shows Indian grouping with Western digits (A-27).
- **Copy:** savings and payback are always labelled *"Estimate. Actual savings depend on usage, tariff changes and weather. Not guaranteed."* (§10), in the screen's language and in the PDF.
- **Notifications:** the `quote_sent` notification is simulated. It is written in the homeowner's `preferred_locale` with a masked recipient, and nothing is ever sent.
- **Languages:** staff screens are English (A-28). Homeowner screen 4, the dashboard quote card and the PDF are in en, hi and mr. `npm run check:i18n` must pass.
- **`priced_on`:** today's date in Asia/Kolkata (A-20).
- **Commits:** local only, in plain English, with no push and no co-author lines. Run `ruff format` on touched files only.

## Review Focus

1. **Rules edited after a quote is sent:** `GET /api/quotes/{id}` and the PDF still show the old price and subsidy. Test: `test_quote_survives_rule_changes` (Task 2).
2. **Second quote while the first is open:**
   - The first becomes `superseded`.
   - Accepting the old one returns 409 `QUOTE_SUPERSEDED`.
   - The homeowner's dashboard links to the new one.
   - Test: `test_new_quote_supersedes_and_old_cannot_be_accepted` (Task 2).
3. **An override without a reason:**
   - Preview works.
   - Send returns 422 `OVERRIDE_REASON_REQUIRED`.
   - The builder disables Send until a reason is typed.
   - Test: `test_send_requires_override_reason` (Task 2).
4. **Verified roof under 100 sq ft:**
   - Preview returns 422 `NO_OPTION_FITS`.
   - The builder shows "No system fits the verified roof" and Send is disabled.
   - Test: `test_tiny_roof_has_no_options` (Task 2).
5. **Another homeowner's quote id or PDF:** 404, never 403. Test: `test_foreign_quote_and_pdf_are_404` (Task 2/3).

---

### Task 1: Staff lead API, verification and lead events

**Files:**
- Create: `backend/alembic/versions/0003_staff_verification_and_lead_events.py`, `backend/app/models/lead_event.py`, `backend/app/schemas/staff.py`, `backend/app/api/staff.py`, `backend/app/services/lead_actions.py`
- Modify: `backend/app/models/lead.py`, `backend/app/models/__init__.py`, `backend/app/main.py`
- Test: `backend/tests/integration/test_staff_api.py`

**Interfaces:**
- **Migration 0003:**
  - Table `lead_events(id, created_at, lead_id fk idx, from_status lead_status null, to_status lead_status null, kind text not null, actor_id fk users, note text null)`. Kind is one of `verified | upgraded | closed | quote_sent | quote_accepted`.
  - New `leads` columns: `verified_sanctioned_load_kw numeric(5,2) null check (>0 and ≤100)`, `load_verified_by fk users null`, `load_verified_at timestamptz null`.
  - `CREATE SEQUENCE quote_number_seq`.
- **`lead_actions.py`:**
  - `record_verification(db, lead, actor, roof_area_sqft: Decimal, via: RoofVerifiedVia, sanctioned_load_kw: Decimal | None, notes: str | None) -> Lead`
  - `upgrade_to_visit(db, lead, actor, reason: str) -> Lead`
  - `close_lost(db, lead, actor, reason: str) -> Lead`
  - `effective_sanctioned_load(db, lead) -> tuple[Decimal | None, Literal["staff","bill"] | None]`. The staff value wins over the bill's confirmed value.
  - Errors are `ApiError` with 409 `LEAD_STATUS_CONFLICT` for a disallowed move, and 422 `REASON_REQUIRED`.
- **API:**
  - `GET /api/staff/leads?score=high|low&status=<LeadStatus>` returns `[StaffLeadRow{id, code, homeowner_name, created_at, status, score, score_reasons, recommended_kw, recommendation_status, next_action, flags[]}]`. Sort: high, then low, then null; newest first within each. `draft` is excluded unless `status=draft`. `flags` combines the sizing flags with `bill_unverified` (no confirmed reading).
  - `GET /api/staff/leads/{id}` returns `StaffLeadDetail`: the row fields, plus homeowner `{full_name, phone, email, preferred_locale}`, the lead's declared fields, `sizing_detail`, verification fields, `sanctioned_load{value, source}`, `current_reading` (the `ReadingOut` shape from `app/schemas/bills.py`), `events[]` and `quotes[{id, number, status, sent_at, selected_kw}]`.
  - `POST /api/staff/leads/{id}/verification` with body `{roof_area_sqft gt0 le100000, via: "survey"|"call", sanctioned_load_kw?: gt0 le100, notes?: ≤2000}`.
  - `POST /api/staff/leads/{id}/upgrade` with body `{reason}`.
  - `POST /api/staff/leads/{id}/close` with body `{reason}`.
  - All require `require_roles("sales","admin")`.

- [ ] **Step 1: Write the failing tests** in `test_staff_api.py`. Use the seeded leads and the `make_staff`/`sign_in` helpers from `test_bills_api.py`.
  - `test_inbox_orders_high_first_then_newest`: seeded Prashant (high) comes before Ayesha and Rohit (low); drafts are hidden.
  - `test_inbox_filters_by_score_and_status`.
  - `test_homeowner_cannot_use_staff_api`: 403 on list, detail and verification.
  - `test_detail_shows_ai_and_confirmed_values_and_reasons`.
  - `test_verification_moves_to_surveyed_and_logs_event`: roof 450 via survey with load 3 → status `surveyed`, one event with kind `verified`, `sanctioned_load == {"value": "3", "source": "staff"}`.
  - `test_upgrade_requires_reason_and_only_from_call_pending`: "" → 422 `REASON_REQUIRED`; called on a `survey_pending` lead → 409.
  - `test_close_lost_with_reason_is_terminal`: after closing, verification returns 409.
- [ ] **Step 2: Run them.** `uv run pytest tests/integration/test_staff_api.py -q`. Expected: FAIL (404 routes).
- [ ] **Step 3: Implement** the migration, the model, the schemas, the services and the routes. Lock the lead with `with_for_update` in every action.
- [ ] **Step 4: Run** `uv run pytest -q`, `uv run alembic upgrade head`, `uv run alembic check` and `uv run ruff check .`. Expected: everything passes and there is no drift.

### Task 2: Quote service: preview, send (snapshot), supersede, accept

**Files:**
- Create: `backend/app/services/quotes.py`, `backend/app/services/notify.py`, `backend/app/schemas/quotes.py`, `backend/app/api/quotes.py`
- Modify: `backend/app/api/staff.py` (preview and send routes), `backend/app/schemas/leads.py` (add `current_quote`), `backend/app/api/leads.py`
- Test: `backend/tests/integration/test_quotes_api.py`

**Interfaces:**
- **Consumes:** `build_quote_options`, `QuoteInputs`, `Overrides`, `QuoteOptions`, `CALC_VERSION` (`app/services/calc/engine.py`), `load_settings`/`load_price_rules`/`load_subsidy_rules` (`rules_repo.py`), and `effective_sanctioned_load` (Task 1).
- **Produces:**
  - `OverrideIn{field: Literal["usable_generation_pct","fixed_charge_monthly","savings_rate"], value: Decimal, reason: str | None}`.
  - `preview(db, lead, overrides: list[OverrideIn], on: date) -> QuoteOptions`.
  - `snapshot_of(result: QuoteOptions, *, lead, reading_id, overrides: list[OverrideIn], actor_id, sanctioned_load_source) -> dict`. It is JSON-safe: every Decimal is a plain string and every date is ISO. It has the keys from §11: `calc_version, priced_on, inputs, settings, price_rules_used[], subsidy_rule, overrides[{field,from,to,by,reason}], assumptions, sizing{final_kw, provisional_kw, required_kw_exact, kw_by_usage, kw_by_roof, flags}, removed[], options[{kw, recommended, gross, subsidy{status,amount,capped}, net, savings{annual_generation, usable_generation, usable_generation_pct, fixed_charge, fixed_charge_source, savings_rate, annual_savings, status, reason}, payback{years,status}, flags}]`.
  - `send_quote(db, lead, actor, overrides) -> Quote`. In one transaction:
    1. Lock the lead.
    2. Check the status allows sending.
    3. Require a reason on every override (`OVERRIDE_REASON_REQUIRED`).
    4. Compute the quote.
    5. Supersede the open quote: insert the new one, then set the old one's `status=superseded`, `superseded_at` and `superseded_by_quote_id`.
    6. Number it `HF-Q-{yyyy}-{nextval:06d}`.
    7. Set `lead.status = quoted` and write a `quote_sent` event.
    8. Call `notify.quote_sent(db, lead, quote)`.
  - `accept_quote(db, quote, homeowner, selected_kw: Decimal) -> Quote`:
    - `QUOTE_SUPERSEDED` (409) when the quote is superseded; `QUOTE_ALREADY_ACCEPTED` (409) when already accepted.
    - `OPTION_NOT_OFFERED` (422) when `selected_kw` is not among the snapshot's options.
    - Otherwise it sets `lead.status = accepted` and writes an event.
  - `notify.quote_sent(db, lead, quote) -> Notification`:
    - Channel `whatsapp`; locale is the homeowner's `preferred_locale`.
    - `recipient_masked` is `+91 ••••• •4821` style, or the masked email when there is no phone.
    - The message uses templates in en, hi and mr with `{code}`, `{kw}` and `{net}`.
  - `QuoteView` (from the snapshot only): `{id, number, status, lead_id, lead_code, sent_at, priced_on, selected_kw, accepted_at, recommended_kw, options[...], removed[], assumptions[], overrides[], fixed_charge_source, subsidy_note}`.
- **Routes:**
  - `POST /api/staff/leads/{id}/quote-preview {overrides}` returns `QuotePreviewOut`: the options as in the snapshot, plus `recommended_kw`, `provisional_kw`, `removed`, `max_allowed_kw` and `sanctioned_load{value,source}`. Calc errors come back as 422 `{code}`.
  - `POST /api/staff/leads/{id}/quotes {overrides}` returns 201 `QuoteView`.
  - `GET /api/quotes/{id}` returns `QuoteView` (owner or staff).
  - `POST /api/quotes/{id}/accept {selected_kw}` is homeowner-owner only.
  - `LeadMine.current_quote: {id, status} | null`: the newest non-superseded quote.

- [ ] **Step 1: Write the failing tests** in `test_quotes_api.py`. Fixture: seed, a homeowner lead confirmed at 340 units and ₹3,200, then a staff member verifies a 450 sq ft roof with a 5 kW load.
  - `test_preview_offers_2_3_4_for_prashant`: offered kW are `["2","3","4"]` and 3 is recommended. For 3 kW: gross "180000", subsidy "78000", net "102000", annual_savings "33909", payback "3.0".
  - `test_load_3kw_removes_4kw`: verify with load 3 → offered `["2","3"]`; removed contains `{"kw":"4","reason":"sanctioned_load"}`.
  - `test_tiny_roof_has_no_options`: roof 80 → preview returns 422 `NO_OPTION_FITS`.
  - `test_preview_requires_verified_roof`: 422 `ROOF_NOT_VERIFIED`.
  - `test_send_requires_override_reason`: an override with no reason → 422 `OVERRIDE_REASON_REQUIRED`. With a reason, the snapshot's `overrides[0]` has from "150", to "180", the user id as `by`, and the reason.
  - `test_send_creates_numbered_quote_event_and_notification`: number matches `^HF-Q-\d{4}-\d{6}$`; lead is `quoted`; one notification in the homeowner locale with a masked recipient.
  - `test_quote_survives_rule_changes`: send, then raise the price rule to 70000 via ORM (close the old rule and add a new one), then `GET` still shows gross "180000".
  - `test_new_quote_supersedes_and_old_cannot_be_accepted`.
  - `test_accept_only_offered_option`: "7" → 422 `OPTION_NOT_OFFERED`; "3" → 200; lead is `accepted`; a second accept → 409.
  - `test_snapshot_cannot_be_updated`: an ORM update to `snapshot` raises (QUOTE_IMMUTABLE from the trigger).
  - `test_foreign_quote_and_pdf_are_404`: quote part.
  - `test_tenant_cannot_be_quoted`: 422 `NOT_QUOTABLE_TENANT`.
  - `test_lead_mine_shows_current_quote`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `quotes.py`, `notify.py`, the schemas and the routes. Map `CalcError` to `ApiError(422, code)`. Map the trigger's psycopg errors to `ApiError(409, "QUOTE_IMMUTABLE")`.
- [ ] **Step 4: Run** the full suite and ruff. Expected: PASS.

### Task 3: Quote PDF in en, hi and mr

**Files:**
- Create: `backend/app/assets/fonts/{Mukta-Regular.ttf, Mukta-SemiBold.ttf, OFL.txt}`, `backend/app/services/pdf/__init__.py`, `backend/app/services/pdf/quote_pdf.py`, `backend/app/services/pdf/strings.py`
- Modify: `backend/pyproject.toml` (add `uharfbuzz>=0.40`), `backend/app/api/quotes.py`
- Test: `backend/tests/integration/test_quote_pdf.py`

**Interfaces:**
- `render_quote_pdf(view: QuoteView, locale: Literal["en","hi","mr"]) -> bytes`. Layout, in order:
  1. The HelioFlow wordmark and the quote number.
  2. Three stacked figures: size, cost after subsidy, payback (estimate).
  3. An options table.
  4. A breakdown for the selected or recommended option.
  5. Assumptions and the disclaimer footer, including the subsidy source note.
- Fonts: Mukta and Mukta-SemiBold, registered once. **Paragraphs only, with `shaping=1`.** Money is formatted `₹1,02,000` in every locale.
- `GET /api/quotes/{id}/pdf?lang=en|hi|mr` returns `application/pdf` with `Content-Disposition: inline; filename="<number>.pdf"`. Without `lang`, it uses the homeowner's `preferred_locale`.

- [ ] **Step 1: Failing tests:**
  - `test_pdf_renders_in_each_language[en|hi|mr]`: the bytes start with `%PDF`, and pypdf extracts the quote number and "1,02,000".
  - `test_pdf_uses_snapshot_after_rule_change`.
  - `test_foreign_quote_and_pdf_are_404`: PDF part.
- [ ] **Step 2: Implement.** Run the tests. Render one PDF per language to PNG with pypdfium2 and **inspect them visually** (conjuncts and matras). Report the result honestly.

### Task 4: Staff screens: inbox and lead detail with quote builder (English)

**Files:**
- Create: `frontend/lib/staff.ts`, `frontend/app/[locale]/(staff)/staff/leads/[id]/page.tsx`, `frontend/components/staff/{lead-row,score-badge,bill-compare,verification-form,quote-builder,lead-actions}.tsx`
- Modify: `frontend/app/[locale]/(staff)/staff/leads/page.tsx`

**Interfaces:** typed hooks `useStaffLeads(filters)`, `useStaffLead(id)`, `useVerify(id)`, `useUpgrade(id)`, `useClose(id)`, `useQuotePreview(id, overrides)` (debounced 300 ms, `placeholderData: keepPreviousData`) and `useSendQuote(id)`. Shapes mirror Tasks 1–2.

- [ ] **Inbox:**
  - Filter chips for score (All / High / Low) and status.
  - A table on desktop and cards below 768 px, with code, name, score badge (High in teal, Low in amber), reasons in words, recommended kW (with "provisional"), next action, flags and age.
  - Loading, empty and error states. Rows link to the detail page.
- [ ] **Lead detail:**
  - **Header:** code, name, a `tel:` link on the phone, status, score.
  - **Bill:** the preview beside a table of field, AI value and confidence, confirmed value, plus an edited marker and flags.
  - **Score reasons** and the sizing detail.
  - **Verification form:** roof, via, load (prefilled from the bill), notes.
  - **Actions:** upgrade (reason dialog) and close lost (reason dialog).
  - **Quote builder:**
    - A banner explains why sending is blocked (ROOF_NOT_VERIFIED, SANCTIONED_LOAD_UNKNOWN, NO_OPTION_FITS).
    - Option cards show gross, subsidy, net, annual savings and payback, and mark the recommended one.
    - A "Removed: 4 kW (sanctioned load is 3 kW)" line.
    - An overrides panel, three optional fields, each with a reason.
    - Send is disabled while any override lacks a reason.
    - A quote history with links to each quote's PDF.
- [ ] **Verify:** `npm run typecheck`, `npm run lint`, `npm run build`.

### Task 5: Homeowner screen 4 and the dashboard quote card (en, hi, mr)

**Files:**
- Create: `frontend/app/[locale]/(homeowner)/my/quote/[id]/{page.tsx,quote-screen.tsx}`, `frontend/components/quote/{quote-hero,option-picker,breakdown}.tsx`
- Modify: `frontend/lib/leads.ts` (`QuoteView`, `useQuote`, `useAcceptQuote`; `LeadMine.current_quote`), `frontend/app/[locale]/(homeowner)/my/page.tsx`, `frontend/messages/{en,hi,mr}.json` (namespace `quote`, plus `dashboard.quote*`, plus errors `QUOTE_SUPERSEDED`, `QUOTE_ALREADY_ACCEPTED`, `OPTION_NOT_OFFERED`)

- [ ] **Screen 4:**
  - A night-teal hero with three stacked figures: size, cost after subsidy, payback "estimate".
  - An option picker (radio cards) where the hero figures follow the selection.
  - "See how we calculated this" opens the breakdown: gross, subsidy (with the source note), net, generation, usable share, savings rate, fixed charge and its source.
  - The assumptions and the estimate disclaimer.
  - A *Download PDF* link that opens `/api/quotes/{id}/pdf?lang={locale}`.
  - *Accept quote*, with a confirm step naming the chosen kW.
  - States: accepted ("We'll contact you about the advance"), superseded ("This quote was replaced", linking to the current one), and a 404 view.
- [ ] **Dashboard:** when `current_quote` is set, show the card "Your quote is ready" (sent) or "Quote accepted, we'll contact you about the advance" (accepted). It links to screen 4.
- [ ] **Verify:** check:i18n passes and there is no hard-coded English in the homeowner namespaces.

### Task 6: Verification, review and commits

- [ ] Backend: the suite, ruff, `alembic check`.
- [ ] Frontend: typecheck, lint, i18n, build.
- [ ] Playwright, with `AI_MODE=demo` and dev servers:
  1. A homeowner submits and confirms the sample bill.
  2. Sales verifies a 450 sq ft roof with a 3 kW load.
  3. The preview shows 2 and 3 kW with 4 kW removed.
  4. An override without a reason blocks Send; adding a reason allows it.
  5. Send, then the homeowner sees screen 4 in Hindi at 390 px, downloads the PDF and accepts 3 kW.
  6. The dashboard shows the accepted card.
  - Take screenshots of the inbox (desktop and phone), the lead detail and builder, screen 4 in all three languages, and the PDF in all three languages.
- **Decisions made during build (noted after review):**
  - The default inbox hides `closed_lost` as well as `draft`; both can still be filtered for.
  - The snapshot records the provisional kW under `inputs.provisional_kw`, not `sizing`.
  - Homeowner quote views drop the override author and reason; staff see both.
- [ ] A fresh reviewer, then a fix pass, then local commits, for example: "Added the staff inbox and lead verification", "Added quotes with immutable snapshots", "Added the quote PDF in three languages", "Built the quote builder for sales", "Added the quote screen for homeowners".
