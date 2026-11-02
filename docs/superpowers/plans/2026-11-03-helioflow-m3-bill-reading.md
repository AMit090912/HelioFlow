# HelioFlow M3 — Bill Upload and AI Bill Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A homeowner (or staff) uploads an electricity bill as an image or PDF. It is validated and cleaned, checked for photo quality, and read by AI (Groq → Gemini → manual entry) in the background. The person then confirms or corrects the values. The lead is never lost.

**Architecture:**
- `app/services/uploads/` validates and normalises files (pure, Pillow/pypdf/pypdfium2).
- `app/services/ai/` holds the provider chain (httpx, JSON mode, strict Pydantic schema) and the sanity checks.
- `app/api/bills.py` exposes upload (202), polling, preview and confirm.
- Extraction runs as a FastAPI background task, using a session factory and provider chain taken from `app.state`, so tests can inject both.

**Spec:** `docs/ARCHITECTURE.md` §5 (upload architecture), §6 (AI extraction and fallback), §3.3/§3.4 (bill_files, bill_readings), §14 (security), §15.2/§15.3 (tests).

## Global Constraints
- The bytes are checked first: magic bytes must say PDF/JPEG/PNG/WebP. The extension and Content-Type are ignored. Max 10 MB (`MAX_UPLOAD_MB`), enforced while reading.
- Images are always re-encoded, which removes EXIF/GPS. PDFs: encrypted → `PDF_ENCRYPTED`, unparsable → `PDF_CORRUPT`, more than 20 pages → `PDF_TOO_MANY_PAGES`.
- Only the 1–2 most relevant pages or images are sent to an AI provider, never the whole PDF.
- Provider order: Groq, then Gemini (one retry on 429/5xx/timeout, honouring Retry-After ≤ 5 s), then `failed_manual`. Every attempt is recorded with provider, model, prompt version, ms, outcome and error code. Raw responses are stored and never logged.
- Model names come from env. Defaults, verified against the live accounts on 2026-11-03: `GROQ_VISION_MODEL=qwen/qwen3.8-27b`, `GROQ_TEXT_MODEL=openai/gpt-oss-120b`, `GEMINI_MODEL=gemini-2.5-flash`.
- `ai_values` (what the AI said) are never overwritten. Confirmed values go into the typed columns, with `edited_fields`.
- Dedupe is by sha256 **per lead only**, never across users.
- `AI_MODE=demo` uses fixtures for the synthetic sample bills and is labelled `is_demo`. `AI_MODE=test` uses injected fakes. `live` is the default.
- Claude makes local commits only at the end of the milestone, using plain-English messages and no trailers. It never pushes.

## Review Focus
1. A phone photo with EXIF rotation must be stored upright, with GPS removed.
2. A PDF with a text layer but no bill keywords (e.g. a cover page) must fall back to rendering pages for vision, not send empty text.
3. A provider returning valid JSON with wrong types (`"units": "three hundred"`) must count as an invalid response and move to the next provider.
4. Uploading the same file twice to the same lead returns the same reading and makes no second AI call. The same file on another lead is read again.
5. A reading stuck in `processing` (server restarted mid-read) becomes `failed_manual` once it is more than 2 minutes old, so the homeowner can type the values in.

---

### Task 1: Dependencies, settings, synthetic fixtures
**Files:** `backend/pyproject.toml` (pillow, pypdf, pypdfium2, httpx, reportlab), `app/core/config.py` (AI settings with defaults; empty env strings fall back to the default), `.env.example`, `backend/scripts/make_bill_fixtures.py`, `backend/tests/fixtures/bills/*`
- [ ] The fixtures script draws a fictional "Sample DISCOM" bill (no real branding or data) and writes `clear.jpg`, `blurry.jpg`, `dark.jpg`, `tiny.png`, `rotated_exif.jpg` (with orientation and GPS tags), `bill.webp`, `text.pdf` (ReportLab, real text), `scanned.pdf` (image only), `multipage.pdf` (cover + bill), `cover_only_text.pdf`, `encrypted.pdf`, `corrupt.pdf`, `fake.jpg` (a renamed EXE header).

### Task 2: Upload validation and normalisation
**Files:** `app/services/uploads/{__init__,errors,sniff,images,pdfs,quality}.py`; `tests/unit/uploads/*`
**Produces:**
- `sniff(data) -> Kind` (`jpeg` | `png` | `webp` | `pdf`; anything else raises `UploadError("FILE_TYPE_UNSUPPORTED")`)
- `normalise_image(data) -> NormalisedImage(jpeg: bytes, preview_png: bytes, width, height)`
- `inspect_pdf(data) -> PdfInfo(page_count, pages_text: list[str])`
- `relevant_text_pages(info) -> list[int]` (keyword score, max 2, empty if not text-based)
- `render_pages(data, pages) -> list[NormalisedImage]` (200 DPI, ≤ 2,500 px long side)
- `check_quality(img) -> Quality(ok, reasons, metrics)` (short side ≥ 700, brightness 40–235, edge variance ≥ threshold calibrated on fixtures)
- [ ] Tests (RED → GREEN): every fixture, plus oversize (10 MB + 1 byte → `FILE_TOO_LARGE`) and EXIF orientation applied with GPS removed. Commit at the end of the milestone.

### Task 3: AI schema, prompt, providers, chain, sanity checks
**Files:** `app/services/ai/{__init__,schema,prompt,providers,chain,validation,demo}.py`; `tests/unit/ai/*`
**Produces:**
- `BillExtraction` (strict Pydantic, §6.1)
- `PROMPT_VERSION = "bill-v1"`
- `Provider` protocol: `name`, `model`, `extract(images=..., text=...) -> dict`; raises `ProviderError(kind, status, retry_after)`
- `GroqProvider` / `GeminiProvider` (httpx; keys only in headers)
- `run_chain(providers, *, images, text, sleep) -> ChainResult(extraction | None, provider, model, attempts)`
- `sanity_flags(extraction, declared_bill) -> dict[str, list[str]]`
- `suggested_average_units(extraction) -> (Decimal | None, method)`
- [ ] Tests: request shapes via `httpx.MockTransport` (Groq JSON mode with an image data URL; Gemini `x-goog-api-key` header, with no key in the URL); the chain covers Groq OK, Groq 429 → retry → Gemini, Groq bad JSON → Gemini, wrong types → next, both fail → None, and every attempt recorded; sanity rules match the §6.3 table; the average uses ≥ 3 months, otherwise current units.

### Task 4: Bills API (upload, poll, preview, confirm)
**Files:** `app/schemas/bills.py`, `app/services/bill_reading.py` (orchestration, background job, stale sweep), `app/api/bills.py`, `app/main.py`; `tests/integration/test_bills_api.py`
**Produces:**
- `POST /api/leads/{lead_id}/bills` → 202 `ReadingOut` (or 200 with the existing reading on a duplicate). A quality failure returns `needs_reupload` with reasons and makes no AI call. Upload rate limit: 10 per hour per user (`RATE_LIMITED`).
- `GET /api/bills/{id}` → `ReadingOut` (status, quality reasons, AI values with confidence, flags, suggested average, confirmed values, attempts summary, `is_demo`). A stale `processing` reading → `failed_manual`.
- `GET /api/bills/{id}/preview` → PNG with `Cache-Control: private, no-store` and `nosniff`.
- `POST /api/bills/{id}/confirm` → validated values; sets the typed columns, `edited_fields`, `confirmed_by/at`, status `confirmed`, and `lead.current_bill_reading_id`. Works after `failed_manual` too (`source_path=manual`).
- Ownership: a homeowner sees only their own lead's readings (404 otherwise); staff see all.
- [ ] Tests: the full upload → background → poll flow with fake providers; duplicate → same id and one AI call; blurry → `needs_reupload` with 0 AI calls; `.exe` → 415; 10 MB + 1 → 413; encrypted → 422; another homeowner → 404 on get/preview/confirm; both providers fail → `failed_manual`, then manual confirm succeeds; stale reading → `failed_manual`; confirm records edits.

### Task 5: Live check and docs
- [ ] One **real** extraction of `clear.jpg` through Groq (and one through Gemini), run manually with the keys. Report the actual fields, confidence and timing honestly. Update ARCHITECTURE Q-9/§6 notes with the chosen models. Make the milestone commits.
