# HelioFlow M6: Projects, Status Link, Notifications and Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:**
- Sales records the (simulated) advance on an accepted quote. That creates a project and a public status link.
- Sales then moves the project through the six stages. Each stage change writes an event and a simulated message in the homeowner's language.
- Anyone holding the link sees a privacy-safe status page in en, hi or mr.
- The homeowner's dashboard shows the project.
- The admin edits the dated price and subsidy rules and the settings, and overlaps are refused with a clear message.

**Architecture:**
- **Backend:** a `projects` service owns the advance, stage moves (forward one step, or back with a reason), the status token (only its SHA-256 is stored), and events plus notifications.
  - Staff routes live under `/api/staff/projects`.
  - The public route is `/api/public/status/{token}`, rate-limited to 30/min per IP and sent with `no-referrer` and `noindex` headers.
  - Rule editing routes live under `/api/rules/*`. Editing is admin-only; sales can view.
- **Frontend:**
  - Staff (English): "Record advance" on the lead page, a new Projects screen (table plus detail panel), and a Rules screen.
  - Public: `/[locale]/s/[token]`.
  - Homeowner: a project card on `/my`.

**Spec:** `docs/ARCHITECTURE.md`:
- §2 screens 5, 8 and 9; the homeowner journey.
- §3.9–3.11, §4 permission matrix, §9.3 (effective-date and overlap behaviour).
- §12 (project lifecycle and status link), §13 (notifications), §14 (headers and privacy).
- Assumptions A-21 (advance amount entered by sales) and A-22 (six stages).

## Global Constraints

- **Stages, in this exact order:** `advance_received → installation_scheduled → installation_completed → net_metering_completed → subsidy_applied → subsidy_credited` (terminal).
  - Forward moves are exactly one step.
  - A backward correction goes exactly one step back and needs a reason (min 5 chars).
  - Error codes: 409 `STAGE_NOT_NEXT`; 422 `REASON_REQUIRED`.
- **Record advance:**
  - Only on a lead with status `accepted` and an accepted quote; otherwise 409 `LEAD_STATUS_CONFLICT`.
  - Amount must be > 0 and ≤ the accepted option's net cost (`ADVANCE_TOO_LARGE`).
  - The reference is generated as `SIMULATED-` plus 8 uppercase hex characters.
  - It creates the project (stage `advance_received`), the first event and a token, and moves the lead to `converted`.
  - The token is returned **once** in the response.
- **Status token:**
  - Generated with `secrets.token_urlsafe(32)`; only `sha256` hex is stored.
  - **Regenerate** revokes the old token and returns a new one, once. **Revoke** sets `status_token_revoked_at`.
  - A revoked, unknown or malformed token returns 404 `LINK_INACTIVE`, which shows the same neutral page in every case.
- **Public payload:** only `{first_name, code, current_stage, stages: [{stage, done_at|null}], scheduled_for|null}`. It must never contain a phone, address, email, money, consumer number or bill.
- **Notifications (simulated, §13):**
  - **On project creation:** type `status_link`. Its message names the link, but the stored text shows `…/s/••••` and never the token, because the outbox is a database table (decision D-1).
  - **On every stage change:** type `stage_changed`.
  - Templates exist in en, hi and mr, and the homeowner's `preferred_locale` picks one.
- **Optional installation date:** the stage-2 move accepts `scheduled_for` (a date, not in the past). It is stored on the event.
- **Rules (§9.3):**
  - New price and subsidy rules can be created.
  - Closing a rule means setting `effective_to` (≥ `effective_from`).
  - An overlap is caught by the database EXCLUDE constraint and returned as 409 `RULE_OVERLAP` naming the conflicting dates.
  - Subsidy slabs are validated: they start at 0, are contiguous and non-negative.
  - Settings update one key at a time, validated against `BusinessSettings`. An invalid value returns 422 `SETTING_INVALID`.
  - Sales can GET; only admin can write (403 otherwise).
- **Copy and headers:** the status page and the homeowner card are in en, hi and mr, and `check:i18n` must pass. `/[locale]/s/*` responses carry `Referrer-Policy: no-referrer` and `X-Robots-Tag: noindex`.
- **Commits:** local only, in plain English. Run ruff format on touched files only.

**Decision D-1 (documented):** a simulated message can't safely contain a live token, because the outbox is readable by every staff member. Staff copy the link once from the project panel and share it. The homeowner also sees the same stages on their own authenticated dashboard.

**Known limitation (after review):** API access logs redact status tokens (`/status/****`). The hosting platform's own request logs for `/<locale>/s/<token>` page views (e.g. Vercel) are outside the app's control. Logs there should be treated as sensitive, and a link can always be regenerated.

## Review Focus

1. **A leaked or old link after regeneration** shows "no longer active", and the new link works. Test: `test_regenerate_revokes_old_token`.
2. **Two staff move the stage at once**, or someone double-clicks: the move happens once and the second gets 409. Test: `test_stage_move_is_one_step_and_locked`, plus the frontend disables the button while pending.
3. **Status page payload:** contains no personal or financial data. Test: `test_public_status_has_no_personal_data` (assert the JSON keys exactly).
4. **An admin closes a rule so it overlaps another** (rather than creating one): the result is 409 `RULE_OVERLAP`, not a 500. Test: `test_closing_rule_into_overlap_is_409`.
5. **The 31st status request in a minute** from one IP gets 429. Test: `test_status_rate_limited`.

---

### Task 1: Projects backend (advance, stages, token, notifications, public status)

**Files:**
- Create: `alembic/versions/0004_project_event_dates.py` (adds `project_events.scheduled_for date null`), `app/services/projects.py`, `app/schemas/projects.py`, `app/api/projects.py` (staff), `app/api/public.py`
- Modify: `app/models/project.py`, `app/services/notify.py` (templates `project_created`, `stage_changed`), `app/schemas/leads.py` + `app/api/leads.py` (`LeadMine.project`), `app/main.py` (status limiter 30/60 s; routers)
- Tests: `tests/integration/test_projects_api.py`

**Interfaces:**
- **`projects.py`:**
  - `record_advance(db, lead_id, actor, amount: Decimal) -> tuple[Project, str]` (project, raw token)
  - `move_stage(db, project_id, actor, to: ProjectStage, note: str | None, scheduled_for: date | None) -> Project`
  - `regenerate_link(db, project_id, actor) -> str`
  - `revoke_link(db, project_id, actor) -> None`
  - `public_status(db, token: str) -> dict`
- **Staff routes:**
  - `POST /api/staff/leads/{id}/advance {amount}` → 201 `{project: ProjectDetail, status_token}`
  - `GET /api/staff/projects` → `[ProjectRow{id, lead_id, code, homeowner_name, stage, stage_changed_at, days_in_stage, selected_kw}]`
  - `GET /api/staff/projects/{id}` → `ProjectDetail{…row, advance_amount, advance_reference, events[], notifications[], link: {active, created_at, revoked_at}}`
  - `POST /api/staff/projects/{id}/stage {to, note?, scheduled_for?}`
  - `POST /api/staff/projects/{id}/link` → `{status_token}`
  - `DELETE /api/staff/projects/{id}/link` → 204
- **Public route:** `GET /api/public/status/{token}`.
- **`LeadMine.project`:** `{stage, stages: [{stage, done_at}], scheduled_for} | null`.

- [ ] **Failing tests** (fixture: the M5 accepted-quote flow):
  - `test_record_advance_creates_project_and_link`: lead → converted; one event; a `status_link` notification whose message lacks the token.
  - `test_advance_only_on_accepted_lead`
  - `test_advance_cannot_exceed_net`
  - `test_stage_move_is_one_step_and_locked`: skipping a stage → 409; the same move twice → 409.
  - `test_backward_needs_reason`
  - `test_schedule_date_on_stage_two`: a past date → 422.
  - `test_stage_change_notifies_in_homeowner_language`
  - `test_public_status_shows_stages`
  - `test_public_status_has_no_personal_data`
  - `test_regenerate_revokes_old_token`
  - `test_revoked_link_is_inactive`
  - `test_status_rate_limited`
  - `test_homeowner_cannot_use_project_api`
  - `test_lead_mine_shows_project`
- [ ] **Implement, then run** the full suite, ruff and alembic check.

### Task 2: Rules admin API

**Files:** `app/api/rules.py`, `app/schemas/rules.py`; test `tests/integration/test_rules_admin_api.py`.

**Routes:**
- `GET /api/rules/price`, `POST /api/rules/price`, `PATCH /api/rules/price/{id} {effective_to}`
- The same three for `/api/rules/subsidy`.
- `GET /api/rules/settings`
- `PUT /api/rules/settings/{key} {value}`

- [ ] **Failing tests:**
  - `test_sales_can_view_admin_can_edit`
  - `test_overlapping_price_rule_is_409`
  - `test_closing_rule_into_overlap_is_409`
  - `test_rule_change_applies_from_its_date`: close the old rule yesterday, add a new one from today, and the preview shows the new price.
  - `test_subsidy_slabs_validated`
  - `test_setting_validated`: `usable_generation_pct` 1.5 → 422; 0.85 → 200, and the change is persisted.
  - `test_unknown_setting_404`
- [ ] **Implement and run.**

### Task 3: Staff frontend: record advance, Projects screen, Rules screen

**Files:**
- Create: `lib/projects.ts`, `lib/rules.ts`, `app/[locale]/(staff)/staff/projects/page.tsx`, `app/[locale]/(staff)/staff/rules/page.tsx`, `components/staff/{advance-form,project-panel,status-link-box,rules-tables}.tsx`
- Modify: the staff layout NAV (Leads, Projects, Rules) and the lead page (an advance form when the status is `accepted`; a link to the project when `converted`).

- [ ] **Projects:**
  - A table sortable by days in stage (desktop) and cards (phone).
  - The panel shows the stage stepper, "Move to <next stage>" (with a date picker on stage 2), "Correct to <previous>" (with a reason), the event history, the simulated notifications each with a grey "Simulated, not sent" badge, and the status link box.
  - The link box offers copy (shown once after generating), regenerate and revoke.
- [ ] **Rules:**
  - Price rules, subsidy rules (slabs shown as text) and settings, each with an inline add form, "close on date", and an inline 409/422 message.
  - Admins edit; sales see a read-only notice.
- [ ] **Run** typecheck, lint and build.

### Task 4: Public status page and the homeowner project card (en, hi, mr)

**Files:**
- Create: `app/[locale]/s/[token]/{page.tsx,status-view.tsx}`, `components/illustrations/spot.tsx` (`SpotProgress`)
- Modify: `next.config.ts` (headers for `/:locale/s/:path*`), `app/[locale]/(homeowner)/my/page.tsx`, `messages/*.json` (namespace `project`, plus `errors.LINK_INACTIVE` and `RATE_LIMITED`, which already exists)

- [ ] **Status page:**
  - No sign-in required; the language switcher is available.
  - Shows the first name, code, a stage timeline with dates and the current stage.
  - An inactive link shows a neutral page.
  - `generateMetadata` sets robots noindex.
- [ ] **Dashboard:** when `lead.project` is set, show a project timeline card, replacing the quote card, with the note "Updates would be sent to your WhatsApp (demo)".
- [ ] **Run** check:i18n and build.

### Task 5: Verification, review and commits

- [ ] Backend suite, ruff and alembic; frontend typecheck, lint, i18n and build.
- [ ] Playwright:
  1. An accepted quote, then sales records the advance and copies the link.
  2. Sales moves to stage 2 with a date.
  3. The public page shows it in Marathi at 390 px.
  4. Sales regenerates the link; the old one shows inactive.
  5. The homeowner dashboard shows the project in Hindi.
  6. The admin adds an overlapping rule and sees the inline 409.
  - Take screenshots throughout.
- [ ] A fresh reviewer, then a fix pass, then local commits.
