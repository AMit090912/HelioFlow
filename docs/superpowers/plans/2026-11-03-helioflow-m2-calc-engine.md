# HelioFlow M2 — Calculation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A pure, deterministic calculation engine (sizing, lead scoring, quote options, pricing, effective-dated subsidy, generation, savings, payback), plus a repository that loads rules and settings from Postgres into it.

**Architecture:** `app/services/calc/` holds pure functions over frozen dataclasses: no I/O, no AI, `Decimal` only. `app/services/rules_repo.py` is the only DB-aware part; it turns ORM rows into engine dataclasses and validates settings with Pydantic. M5's quote builder will call `engine.build_quote_options()` and snapshot its result.

**Spec:** `docs/ARCHITECTURE.md` §7 (scoring), §8 (sizing and options), §9 (pricing and subsidy), §10 (savings and payback), §15.1 (tests), §17 (assumptions).

## Global Constraints
- No floats anywhere in `services/calc` (a test asserts every numeric output is `Decimal` or `int`).
- Rounding happens only at outputs: money is `ROUND_HALF_UP` to ₹1, payback is `ROUND_HALF_UP` to 0.1 years, kWh is a whole number. Intermediate values keep full precision.
- Payback is net cost ÷ the *rounded* annual savings, so displayed numbers reconcile.
- Rule effective dates are inclusive at both ends; `effective_to = None` means open-ended. If no rule matches, raise `PRICE_RULE_MISSING` / `SUBSIDY_RULE_MISSING`. Never silently fall back to an expired rule or to zero.
- Errors carry API-ready codes (`USAGE_UNKNOWN`, `ROOF_NOT_VERIFIED`, `SANCTIONED_LOAD_UNKNOWN`, `NO_OPTION_FITS`, `INVALID_INPUT`, …).
- Business values come only from `Settings` and rule dataclasses, never from constants in calc code.
- Claude never runs git commit or push. Each task ends by suggesting a commit message to Amit.

## Review Focus
1. Exactly 350 units/month must give 3 kW, not 4 (the Decimal boundary). Test in Task 2.
2. A bill equal to the threshold (₹1,000) scores High, not Low. Test in Task 3.
3. A fixed charge ≥ the bill must give "savings not available", never a negative or a divide-by-zero. Test in Task 5.
4. A quote date exactly on a rule's last day selects that rule; the next day selects the next rule or errors. Test in Task 4.
5. A business property must give a subsidy of ₹0 with status `NOT_ELIGIBLE`, distinct from a missing rule. Test in Task 4.

---

### Task 1: Types, errors, rounding, rule selection
**Files:** `app/services/calc/{__init__,types,errors,rounding,rules}.py`; tests `tests/unit/calc/test_rules.py`
**Produces:**
- `Settings` (frozen) with `generation_kwh_per_kw_year`, `roof_sqft_per_kw`, `min_monthly_bill_for_survey`, `usable_generation_pct`, `default_fixed_charge_monthly`: Decimal; `capacity_options_kw: tuple[Decimal, ...]` sorted; `quote_option_offsets: tuple[int, ...]`.
- `PriceRule`, `SubsidySlab`, `SubsidyRule` (frozen) mirroring §3.5/§3.6.
- `CalcError(code, message, **context)`.
- `rupees(x) -> Decimal` (₹1, HALF_UP), `one_decimal(x)`, `whole(x) -> int`.
- `is_effective(rule, on: date) -> bool`, `select_price_rule(rules, kw, on) -> PriceRule`, `select_subsidy_rule(rules, segment, on, scheme="CENTRAL_RESIDENTIAL") -> SubsidyRule`. More than one match raises `RULE_AMBIGUOUS`.
- [ ] Tests (all of §9.3): boundary start/end inclusive, rule change Nov 30/Dec 1, expired → missing, none → missing, kW outside every price range → `PRICE_RULE_MISSING`, two matches → `RULE_AMBIGUOUS`. Then run (RED), implement, run (GREEN). Commit (Amit): `feat(calc): rule types, rounding and effective-dated rule selection`

### Task 2: Sizing
**Files:** `app/services/calc/sizing.py`; `tests/unit/calc/test_sizing.py`
**Produces:**
- `annual_units(avg_monthly_units) -> Decimal`
- `required_kw(annual, settings) -> Decimal`
- `kw_by_usage(required, settings) -> Decimal` (smallest option ≥ required; the largest option is used when required exceeds it, with flag `usage_exceeds_max_option`)
- `kw_by_roof(area, settings) -> Decimal | None`
- `recommend(ownership, avg_monthly_units, declared_roof_sqft, verified_roof_sqft, sanctioned_load_kw, settings) -> Sizing`, where `Sizing` has `annual_units`, `required_kw`, `kw_by_usage`, `kw_by_roof`, `recommended_kw`, `status` (`provisional` | `final`), `flags` (tuple of str) and `roof_basis`.
- [ ] Tests: the three sample leads (3 provisional, None, 1 provisional) with roof missing; 350 → 3; 351 → 4; roof 250 → 2; roof 99 → None; roof limits usage (need 3, roof 2 → 2); verified roof makes status `final`; sanctioned load below recommendation flags `exceeds_sanctioned_load` without capping; units None → `USAGE_UNKNOWN`; negative units → `INVALID_INPUT`. Commit: `feat(calc): solar sizing with provisional/final roof basis`

### Task 3: Lead scoring
**Files:** `app/services/calc/scoring.py`; `tests/unit/calc/test_scoring.py`
**Produces:** `score_lead(ownership, bill_amount, bill_source, sizing: Sizing | None, settings) -> Score`, where `Score` has `score` (`high` | `low`), `next_action` (`survey_visit` | `call`) and `reasons` (tuple of dicts, each with `code` plus its values: threshold, value, source). Reason codes: `tenant`, `bill_below_threshold`, `roof_too_small`, `usage_unknown`. `sizing` is None when units are unknown.
- [ ] Tests: the samples (High; Low tenant; Low small bill with `{"value": "650", "threshold": "1000", "source": "declared"}`); 999/1000/1001; confirmed bill source recorded; roof too small; usage unknown; multiple reasons combine; never returns a "rejected" state. Commit: `feat(calc): deterministic, explainable lead scoring`

### Task 4: Pricing, subsidy and quote options
**Files:** `app/services/calc/pricing.py`, `app/services/calc/options.py`; tests `test_pricing.py`, `test_options.py`
**Produces:**
- `gross_cost(kw, rule) -> Decimal`
- `subsidy_amount(kw, rule) -> SubsidyAmount(raw, amount, capped)` (linear pro-rata, A-5)
- `subsidy_for(kw, property_type, rules, on) -> Subsidy(status ELIGIBLE | NOT_ELIGIBLE, amount, raw, capped, rule | None)` (home → residential)
- `quote_options(recommended_kw, verified_roof_sqft, sanctioned_load_kw, settings) -> OptionSet(offered: tuple[Decimal], removed: tuple[{kw, reason}], max_allowed_kw)`. Errors: `ROOF_NOT_VERIFIED`, `SANCTIONED_LOAD_UNKNOWN`, `NO_OPTION_FITS`.
- [ ] Tests: subsidy table 0.5/1/2/2.5/3/5 → 15000/30000/60000/69000/78000/78000; synthetic cap rule (0–10 @ 30000, cap 78000; 5 kW raw 150000 → 78000 capped); business → 0 `NOT_ELIGIBLE`; gross 3 × 60000; the four option rows in §10.1 (450/5 → 2,3,4; 450/3 → 2,3 with 4 removed for load; 250/5 → 1,2 with 3 removed for roof; 80 → `NO_OPTION_FITS`); recommended above load is not offered. Commit: `feat(calc): pricing, pro-rata capped subsidy and constraint-filtered options`

### Task 5: Savings, payback and engine orchestration
**Files:** `app/services/calc/savings.py`, `app/services/calc/engine.py`; tests `test_savings.py`, `test_engine.py`
**Produces:**
- `estimate_savings(kw, annual_units, monthly_bill, avg_monthly_units, fixed_charge, fixed_charge_source, settings, overrides) -> Savings(annual_generation: int, usable_generation: Decimal, savings_rate: Decimal | None, annual_savings: Decimal | None, status, reason)`
- `payback(net, annual_savings) -> Payback(years: Decimal | None, status ok | immediate | not_available)`
- `Overrides(usable_generation_pct, fixed_charge_monthly, savings_rate)`, all optional
- `price_option(kw, inputs: QuoteInputs, price_rules, subsidy_rules, settings, on, overrides) -> OptionQuote`
- `build_quote_options(inputs, price_rules, subsidy_rules, settings, on, overrides) -> QuoteOptions` (offered option quotes plus removed, recommended_kw, assumptions ids, calc_version "calc-1.0.0")
- [ ] Tests: Prashant 2/3/4 kW and Ayesha 1 kW rows from §10.1 (gross, subsidy, net, usable, savings, payback exact); usable capped at consumption; extracted fixed charge preferred over the default (source recorded); overrides applied; fixed ≥ bill → `not_available`; savings ≤ 0 → payback `not_available`; net 0 → `immediate`; payback 2.25 → 2.3 (HALF_UP); all numeric outputs are Decimal or int. Commit: `feat(calc): savings and payback estimates and quote option engine`

### Task 6: Rules repository (DB → engine)
**Files:** `app/schemas/settings.py`, `app/services/rules_repo.py`; tests `tests/integration/test_rules_repo.py`
**Produces:**
- `BusinessSettings` (Pydantic; validates each key's type and range)
- `load_settings(db) -> Settings` (a missing key raises `SETTINGS_INCOMPLETE`)
- `load_price_rules(db) -> tuple[PriceRule]`
- `load_subsidy_rules(db) -> tuple[SubsidyRule]` (slabs validated as contiguous from 0)
- [ ] Tests: after seed, settings equal §3.7; rules load; Prashant 3 kW through DB-loaded rules equals the unit-test numbers; a bad slab JSON raises `INVALID_RULE`; a missing setting raises `SETTINGS_INCOMPLETE`. Coverage of `services/calc` ≥ 95%. Commit: `feat(calc): load rules and validated settings from the database`
