## SOP REQUIRED SECTIONS

---

## 1. Document control / metadata

| Field | Value |
|---|---|
| SOP title | _e.g., Standalone Unpaid Absence — Initial Decisioning (Without Manual Applicability)_ |
| Track | Absence / STD / … |
| Sub-track & phase | _e.g., Initial Decisioning, Phase 1_ |
| Version | _e.g., 0.1 (draft)_ |
| Last updated | YYYY-MM-DD |
| Author / owner | |
| Process / business owner | _who owns the business process (may differ from the document author)_ |
| Status | Draft / In review / Approved |
| Source documents | List every doc/transcript/repo file this SOP was built from, with versions |
| Reviewers / sign-off | Business + technical reviewer |
| Review cadence | _how often this SOP is re-reviewed; "To be defined" if unset (log a gap)_ |

---

## 2. Purpose & scope

- **What process this SOP documents** — 2–4 sentences in plain language.
- **Entry paths** — the distinct ways a case can enter this process (e.g., *batch entry* driven by current plan status vs. *evidence-driven entry* triggered by a certification event). Each entry path may run different routing, checks, and exclusions — describe them in a table so the judge can tell which path a trace followed.
- **In scope** — the exact cases this process handles (claim types, coverage codes, plan types, customer set, states, entry paths, etc.). Use a numbered table (IS-1, IS-2, …) so each in-scope item is individually referenceable.
- **Out of scope** — the cases explicitly excluded *and the reason for each* (OS-1, OS-2, …). The out-of-scope list is itself a set of evaluable rules — be precise.
- **Explicitly unclear / unverified scope** — a separate table (UV-1, UV-2, …) for scope assertions that are **plausible but unconfirmed**, each carrying its Gap ID and status. This is where you keep an old draft's "X is out of scope" claim that the current process seems to contradict, instead of silently deleting it or asserting it. (See convention 9.)
- **Boundary with other SOPs/phases** — where this process hands off (e.g., "manual applicability cases are covered by SOP-XYZ"; if that SOP is not yet identified, log a gap).

---

## 3. Governance & ownership

Who is accountable for running, reviewing, and changing this process. A process with no named owner is a risk, so an unfilled RACI is kept as a placeholder with a gap — never omitted.

**3.1 · RACI (roles, accountability, sign-off).** A table mapping each stage (or the whole process) to **Responsible / Accountable / Consulted / Informed**. Name the operations team(s) that action any referral-task queues the process creates, and the criteria they apply. If ownership is unassigned, keep the row with a gap chip.

| Stage | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| _All stages / per stage_ | _[G-xx if unassigned]_ | | | |

**3.2 · SOP review cadence & sign-off.** The review cadence, sign-off workflow, and document-approval / deployment-approval authority. Cross-reference the metadata in Section 1. If undefined, state so and log a gap.

---

## 4. Glossary & key concepts

A table of every domain term and system used, in plain language, so a non-technical reader can follow the rest of the document.

| Term / acronym | Meaning |
|---|---|
| _e.g., Leave plan_ | _A specific benefit a claimant may be entitled to within a case…_ |
| _Applicability_ | _Whether a given leave plan applies to this claim…_ |
| _MLE_ | _Master Level Event — the top-level case record in FINEOS…_ |
| _DPDP_ | _Disability Document Payload — the full claim record fetched from FINEOS…_ |
| _Certified period_ | _The approved date range during which the claimant is entitled to benefits…_ |
| _Referral task_ | _A task created for an operations reviewer to follow up; state whether blocking or non-blocking…_ |
| _Business exclusion_ | _Expected control flow (not a system error) where a case/plan is intentionally not processed further and is logged…_ |

**4.1 · Result vocabulary (standardized).** If every step/gate produces one of a small closed set of results, define that set here **once** and map all synonyms onto it. This removes ambiguity for the judge. Also state cross-cutting matching rules (case-insensitivity, Title-Case convention).

| Standard result | Meaning | Synonyms (all equivalent) |
|---|---|---|
| _e.g._ PASSED | _The gate is satisfied; processing continues._ | _"passed", "resolved"_ |
| _e.g._ SKIPPED | _The gate is not actionable; the plan is excluded from further decisioning at that gate._ | _"non-actionable", "excluded from this phase", "skipped"_ |
| _e.g._ FAILED | _The gate could not be evaluated / produced an unrecognized state; routed to error handling._ | _"processing failure"_ |

---

## 5. Systems & data sources

Describe, functionally, each system the process touches and what role it plays. No code references.

| System | What it is | What the process reads from it | What the process writes to it |
|---|---|---|---|
| FINEOS | Claims system of record | Claim data, case structure, statuses, dates | Final decisions, notes, certified periods, task updates |
| Rules engine / rules database | Evaluates versioned gate/decision rules; stores business rules loaded at runtime | Classification / calculation / eligibility rules | — |
| Configuration store | Customer allow/block/pilot lists, inclusion lists, feature flags | Which customers/plans are processed automatically | — |
| Core Plan configuration | Employer plan terms | Plan type, durations, rate mode | — |
| Knowledge base | Customer/plan/provision rules for deeper (provision-level) evaluation | Provision-level verdicts (eligibility, applicability, certification, concurrence) | — |
| Operational UI automation (browser automation) | Used when no programmatic path exists | — | UI-driven updates (described as literal screen actions) |
| Observability / telemetry | Distributed tracing and metrics over each run | Per-stage / per-plan / per-call trace and metric data | — |

Note per system whether any write path is **not yet fully live in production** (and its manual fallback), and how errors are classified and routed — configuration-driven vs. code-driven. Cross-reference Section 11.

---

## 6. Preconditions & assumptions

The conditions that must hold for the process to run, and the assumptions it is built on. These are often inferred rather than documented — capture them anyway and flag the inference with a gap.

- **Preconditions** — must be true for the process to start (e.g., customer permitted by configuration; required configuration present; FINEOS and supporting services available; any feature flag / enablement in place).
- **Assumptions** — things taken as given (e.g., FINEOS is authoritative for claim state; referral tasks are actioned by an operations team; external-system availability). Each assumption that is not confirmed gets a gap.

---

## 7. Process overview

- **Trigger(s):** what starts the process (e.g., new claim in the intake queue; new evidence uploaded; a batch vs. evidence-driven request). If the upstream trigger is unconfirmed, log a gap.
- **Core stages:** the ordered stage names at a glance (Routing → … → Reporting).
- **Human steps:** whether any step blocks on a human, or only non-blocking referral tasks exist (cross-reference Section 10).
- **End states:** the complete list of ways the process can finish (e.g., *Approved & progressed*, *Denied/Excluded (per plan)*, *Business exclusion (logged)*, *Restriction override applied*, *Technical error*).
- **High-level flow:** a short narrative of the natural progression, followed by a flow diagram (Mermaid or equivalent) showing each step and its exit points, including the shared **error & exclusion handling** target and the terminal **reporting** step. The diagram is for orientation; the authoritative detail lives in Section 8.

---

## 8. Step-by-step procedure (the core)

The process is documented as an ordered list of **steps**. Each step is one decision/action stage. Use the **exact same block** for every step:

### Step block schema

Every step is written as a **function with an explicit state contract**: it assumes a precondition, consumes named inputs, produces a named result, and guarantees a postcondition. The contract fields (Precondition, Postcondition, Output contract) are what let the judge verify that each step's *outputs* legitimately satisfy the next step's *trigger* — i.e. that the trigger-to-output wiring is sound, not just that each step looks right in isolation. Use the **exact same block** for every step, in this field order:

> **Step N — <Step name>**
>
> - **Goal (plain language):** one sentence a non-technical reader understands.
> - **Runs when (entry condition / trigger):** the precise condition under which this step executes (usually "the previous step returned <outcome>", or the routing stage entered directly here).
> - **Entry paths that can trigger this step:** which entry paths (e.g. batch, evidence-driven, sequential-from-Step-N-1) can land here *directly*, and any path-specific behavior. State "sequential only" if it can only be reached from the prior step.
> - **Precondition (assumed true on entry):** the state the step relies on already holding — the named fields/values and prior-step guarantees it does not re-verify. If this is false, the step should not have been triggered (an evaluation checkpoint).
> - **Inputs & sources (consumed):** each value read + where it comes from (system, payload, field). These are *reads only*.
> - **Decision logic / rules (pure evaluation — no external state change):** every rule as `IF <condition on named field> THEN <outcome>`, covering all branches including "otherwise". This is the verdict the step *computes*; it must not include external writes. 
> - **Actions performed (side effects / writes):** what the step *changes* on a pass — every write to FINEOS, the working record, or the UI, described literally (system, screen, field, value, button). Keep this strictly separate from the pure evaluation above; a step may compute a verdict and perform no external write.
> - **Output contract (produces):** each output field this step writes, its **allowed value set / type**, and the **downstream step that consumes it**. This is what ties one step's output to the next step's trigger.
> - **Postcondition (guaranteed true on exit):** the state the step guarantees for every path that leaves it (pass, skip, stop). The next step's Precondition should be a subset of this.
> - **Outcomes & routing:** each possible result and where it goes next (→ next step / → stop / → manual adjudication / → error handling).
> - **Stop / exit conditions:** what causes the process to halt here and exactly what is recorded (note name, task name, status, log entry).
> - **Re-entrancy / idempotency:** whether re-running this step on the same case is safe, and what happens if the target state is already set (matters because routing can enter mid-flow and the evidence-driven path can re-enter). State "not re-entrant" if re-running would double-write or corrupt state.
> - **Human touchpoint (if any):** any task/notification created here, labelled **blocking** or **non-blocking**, and cross-referenced to Section 10.
> - **Why (rationale):** one sentence on the business reason for this step's decision.
> - **Evaluation checkpoints:** atomic, true/false statements the judge can verify against the trace. Include at least one that checks the **postcondition held** and one that checks the **precondition was true on entry**. List one per observable behavior.
> - **Open questions / gaps:** anything unconfirmed (cross-reference Section 17).

Repeat the block for every step, in execution order. Keep step numbering stable across versions (append, don't renumber) so evaluation datasets stay aligned.

**Chaining rule.** Across adjacent steps, everything the next step assumes on entry must already be guaranteed by the previous step's postcondition, and the result named in a step's Output contract must be exactly the field and value the next step's "Runs when" tests. If they don't line up, either a step is missing or a trigger is mis-stated — surface it as a gap rather than papering over it.

### When one step routes to several outcomes (single-point bifurcation)

If a *single* step's decision sends the case to different next steps or terminal states but **does not change which steps exist afterwards**, you do NOT need a fork block. Use the ordinary step block: list every branch in **Decision logic / rules** as `IF … THEN …`, map each to its target in **Outcomes & routing**, and gate any later step with **Runs when**. This already covers the common case (e.g. *Applicable → Step 3; Not Applicable → skip; no active plans → stop*).

### When the process splits into divergent multi-step paths (true bifurcation)

Use a **fork block** only when a discriminator forks the process into **two or more sub-flows that differ in *which steps exist*** (e.g. *natural birth* runs one set of steps, *C-section* runs a different set), which may later rejoin. This keeps the alternative paths visible instead of interleaving them into a misleading linear list.

#### Fork block schema

> **Step N — <Fork name>  [DECISION]**
>
> - **Goal (plain language):** one sentence on what is being decided and why the paths differ.
> - **Runs when (entry condition / trigger):** the precise condition under which the fork is reached.
> - **Precondition (assumed true on entry):** the state that must hold for the fork to be meaningful (e.g. the discriminator field is populated).
> - **Discriminator:** the single named field/value that selects the branch (e.g. *delivery type*, read from <source>), and the list of values it can take.
> - **Branches:** one row per path. Each row gives a **branch key**, its selecting condition, and the sub-step it enters. Cover every value including "otherwise":
>   - `Branch A — <name>`: `IF <discriminator = value> THEN` enter Step N.A1.
>   - `Branch B — <name>`: `IF <discriminator = value> THEN` enter Step N.B1.
> - **Output contract (produces):** the selected branch (one of the branches listed above), read by each sub-step's "Runs when" and by the reconvergence step.
> - **Postcondition (guaranteed true on exit):** exactly one branch is selected and its sub-flow entered; the discriminator value that selected it is recorded.
> - **Reconverges at:** `Step M` where the branches rejoin — or `branches terminate independently — none reconverge` if each path ends in its own terminal state.
> - **Re-entrancy / idempotency:** whether re-evaluating the fork on the same case re-selects the same branch (it should, given a stable discriminator).
> - **Why (rationale):** one sentence on the business reason the paths diverge.
> - **Evaluation checkpoints:** atomic true/false statements — e.g. *"Exactly one branch was taken"*, *"The branch matched the discriminator value"*, *"The discriminator was populated on entry (precondition held)"*.
> - **Open questions / gaps:** anything unconfirmed (cross-reference Section 17).

#### Branch sub-step numbering

- Sub-steps of a fork at Step N are numbered **`Step N.A1`, `Step N.A2`, …** for Branch A; **`Step N.B1`, `Step N.B2`, …** for Branch B; and so on. The letter is the branch, the trailing number is the order within that branch.
- Each sub-step uses the **normal step block** (all the usual fields, including the state-contract fields — Precondition, Output contract, Postcondition) **plus a `Branch:` field** naming its branch key. Its **Runs when** references the fork outcome (e.g. *"Step N selected Branch A (natural birth)"*), and its **Precondition** should assert the branch selection (e.g. *the fork selected Branch A*) so the chaining rule holds across the fork.
- The reconvergence step is an ordinary `Step M` whose **Runs when** names the branches that feed it, e.g. *"any branch completed — Step N.A2 or Step N.B2"*.
- Keep fork and sub-step numbering stable across versions (append branches/sub-steps, never renumber) so evaluation datasets stay aligned.

---

## 9. Business rules reference

A single consolidated table of *every* rule the process relies on, so reviewers can audit the logic in one place and the judge can check deterministic steps. When the rules are evaluated by a shared rules engine against versioned definitions, say so, and use the standardized result vocabulary from Section 4.1.

| Rule ID / Gate | Used in step | Condition | Result | Source | Documented or opaque? |
|---|---|---|---|---|---|
| R-01 | Step 2 | _…_ | _…_ | Rules database | OPAQUE-RULE (see Gap G-xx) |
| R-02 | Step 4 | _…_ | _…_ | SOP-defined | Documented |

Include thresholds, default values, lookup lists, and date-math formulas here even if they also appear inside a step. Note whether a formally numbered external business-rule catalog exists separate from the rule definitions themselves (log a gap if unconfirmed).

---

## 10. Human-in-the-loop / manual review checkpoints

Every point where a human is (or might be) involved, classified by whether the automated flow **waits**.

**10.1 · Blocking approval gates.** Points where the automated flow pauses and waits for a human decision. If none is confirmed, say so explicitly — *"none confirmed"* is not the same as *"none exists"*; log a gap.

**10.2 · Non-blocking checkpoints (task created, process continues).** A table of every task/notification the process creates without waiting on it — the trigger, the task created (system + name), and the step. Make clear that these are non-blocking and, where relevant, created *after* the automated decision purely to route the outcome to operations.

| Trigger | Task created (system + name) | Step | Blocking? |
|---|---|---|---|
| _e.g._ Applicability referral (plan still not Applicable after evaluation) | _"Review Absence" (FINEOS), per-plan, with verdict/reasoning_ | Step 2 | Non-blocking |

**10.3 · Error / exclusion routing.** Confirm that every failure path lands at the shared error & exclusion handling step and hands off to reporting — i.e. the process never stalls waiting on a human.

**10.4 · Re-entry after manual resolution.** State whether a case a human resolved outside the automated flow is expected to re-enter this process (e.g. via the evidence-driven path). If undocumented, flag as a gap — don't assert either way.

---

## 11. Error handling & exclusions

- How **technical / runtime errors** are caught, classified (technical / business / configuration), logged with source stage and cause, and routed to the shared error-handling step.
- How **business exclusions** (out-of-scope cases) are recorded and routed — these are expected control flow, not system errors.
- The single, consistent record format used for traceability (what gets logged, where).
- Whether **task creation is configuration-driven or code-driven** — i.e. whether configuration decides, per error type, if a failure creates a referral task or is log-only, including any global "incident mode" switch or per-error suppression with expiry. State the default (e.g. *log-only unless explicitly configured to create a task*).
- Confirm: are rejected/non-qualifying cases written back to the source system, or only logged? (State explicitly — in the current Absence/STD scope, rejections are *not* written back; if unconfirmed, log a gap.)
- Note that a detailed technical error catalog may be maintained separately by engineering and is intentionally not reproduced in this business/process document.

---

## 12. Operational performance

Targets and monitoring for running the process day to day. Distinguish confirmed monitoring *mechanisms* from unset *target values* — the first can be confirmed while the second is still a gap.

| Aspect | Status |
|---|---|
| SLA / turnaround per stage | _target or [G-xx]_ |
| KPIs & monitoring mechanism | _e.g. distributed tracing/telemetry — Confirmed_ |
| KPI targets/thresholds (STP rate, exclusion rate, override rate, …) | _values or [G-xx]_ |
| Escalation timers (unactioned referral task) | _target or [G-xx]_ |

---

## 13. Compliance & risk

| Aspect | Status |
|---|---|
| Regulatory / policy mapping | _linkage to this process, or [G-xx]_ |
| Data retention / PII handling for claim data | _policy, or [G-xx]_ |

Capture the regulatory obligations this process touches and how claim data (often PII) is retained and handled. If a catalog exists in the organization but its linkage to this process is unconfirmed, record that as a gap rather than assuming coverage.

---

## 14. Operational resilience

| Aspect | Status |
|---|---|
| API retry & backoff (reads/writes) | _Confirmed / [G-xx]_ |
| Authentication-token refresh | _Confirmed / [G-xx]_ |
| Resilience of browser-automation (UI) calls specifically | _[G-xx] if unconfirmed_ |
| Disaster recovery for a system/UI-automation outage | _[G-xx] if unconfirmed_ |
| Rollback procedure for a bad playbook/rule deployment | _[G-xx] if unconfirmed_ |

Programmatic API resilience is often confirmed while UI/browser-automation resilience and DR/rollback posture are not — treat those separately.

---

## 15. End-state catalog

Enumerate every terminal outcome and exactly how it is recorded, so each is independently verifiable. Add an **operator next action** column: for each end state, what an operations reviewer should do next (or "None — automated"). If undefined, keep the column and log a gap.

| End state | When reached | What is recorded (notes, tasks, statuses, eForms) | Operator next action |
|---|---|---|---|
| Approved & progressed | All gates pass for at least one plan | _decision recorded, LR progressed, eForm submitted, task created…_ | _…_ |
| Denied (per plan) | Any gate result FAILED | _…_ | _…_ |
| Excluded (per plan) | Any gate SKIPPED (none FAILED) | _…_ | _…_ |
| Business exclusion (logged) | A scope/customer filter fails | _logged; not written back_ | _…_ |
| Restriction override applied | Only an overridable restriction present | _status updated; continues_ | _None — automated_ |
| Technical error | Runtime failure | _error recorded; task or log-only per config_ | _…_ |

---

## 16. Per-step external system connections

A matrix showing, for each step, which external systems it touches and how. This lets the judge check that a trace hit exactly the systems the step should — no more, no less — and makes the browser-automation (UI) touchpoints explicit.

| Step | FINEOS | Rules engine | Knowledge base | Browser automation (UI) |
|---|---|---|---|---|
| 1 · Routing | _Read full claim payload (conditional)_ | _Customer-filter config_ | — | — |
| 2 · Applicability | _Override (conditional); re-read_ | _Inclusion list_ | _Provision lookups (Group A)_ | — |
| … | … | … | … | … |

Add or rename columns to match the actual systems in Section 5. Mark conditional connections as such.

---

## 17. Open questions & gaps log

A living list of everything that could not be confirmed from source material. This is the deliverable's "spec asks you questions" mechanism — gaps are surfaced, never invented. Each entry is a concrete question to resolve with the client/team, and each inline flag elsewhere in the SOP (see convention 9) has a matching row here.

| Gap ID | Type | Step / rule / section affected | Question to resolve | Owner | Status |
|---|---|---|---|---|---|
| G-01 | OPAQUE-RULE | Step 2 | What are the exact matching conditions for the claim-type classification rule stored in the rules DB (null handling, case sensitivity)? | | Open |
| G-02 | MISSING-DETAIL | Step 5 | Which UI screen/fields are used when no API path exists? | | Open |
| G-03 | AMBIGUITY | Step 7 | Confirm the default value applied when delivery type is unknown. | | Open |

Gap types: `OPAQUE-RULE` (logic hidden in the rules DB), `MISSING-DETAIL` (source docs don't say), `AMBIGUITY` (sources conflict or are unclear), `ASSUMPTION` (we proceeded on an assumption that needs confirmation), `UNVERIFIED` (a plausible claim we could neither confirm nor refute), `LIKELY-OUTDATED` (a carried-over claim the current process appears to contradict), `PRODUCTION-READINESS` (a path not yet fully live), `MISSING-ARTIFACT` (a referenced document/catalog that does not yet exist).

---

## 18. Change log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | YYYY-MM-DD | | Initial draft |

---

## 19. Sources & authority

State what the **authoritative definition** of the process actually is (e.g. the runtime playbook plus its versioned stage-gate rule definitions and customer/knowledge-base configuration), and that this SOP is the **business/process view** of that definition. Note what is intentionally out of scope for this document (e.g. the detailed engineering error catalog, API invocation patterns, testing strategy, maintained separately). This tells a reader which artifact wins if the SOP and the running system ever disagree.

---

## 20. Appendices

Reference material that supports the main body but would clutter it.

**Appendix A · Status value reference.** For each gate/field with a closed set of values, list the full value set (e.g. *Applicability: Applicable, N/A, Not Applicable, Undetermined*). Note the matching convention (case-insensitive; Title Case for readability) once. This is the lookup the judge uses to check that a trace's raw status maps to the right standard result.

**Appendix B · FAQ / troubleshooting.** A business-user-facing guide to interpreting each end state and referral task. If it doesn't exist yet, keep the heading and log a gap.

Add further appendices (worked data examples, message-format samples, etc.) as needed.

---