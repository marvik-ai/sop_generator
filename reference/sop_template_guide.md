# SOP Template & Structure Guide

**Purpose of this document:** Define the standard structure that every claim-adjudication SOP (Absence, STD, and future tracks) must follow. You are producing a **markdown SOP** that is then converted, without human editing, into the standard **interactive HTML SOP template**. The structure below mirrors that template exactly — 15 sections, in this order, with these headings and these tables.

Every SOP serves three consumers:

1. **The HTML renderer (mechanical).** A converter maps your markdown onto the HTML template. If a section is missing, renamed, or a table's columns are reordered, it renders wrong. Structure is not stylistic — it is an interface contract.
2. **The evaluation framework (primary).** An LLM-as-judge reads the SOP plus an agent's execution trace and verifies the agent did *exactly* what the SOP prescribes. Every step must be written as **observable, checkable assertions** — not prose a human "gets the gist" of. The step block is built for this: `Trigger`, `Precondition`, `Output contract`, `Postcondition` and `Stop / exit conditions` are each phrased so the judge can mark them true or false against the trace.
3. **Agent / playbook development (secondary).** A developer reads the SOP to know what to build: every decision, every field, every rule, every write.

> This guide is anchored on the **Absence** track but is track-agnostic. The same structure must be reusable for STD (Maternity Flow 1 today) and any future track, so evaluation is consistent across pipelines.

---

## 0. How to use this guide

- Sections **1–15** are the **required sections** of every SOP. Emit all fifteen, in order, with the exact headings given. A section with nothing in it is emitted with its table headers and a stated reason (`Not applicable — <reason>` or a gap chip), never silently dropped.
- The **step block** in Section 7 is the core. Every step gets one block, always with the same fields, always in the same order.
- Follow the **Writing conventions** (Section A) and the **Definition of Done** (Section C) before considering an SOP finished.
- Anything you cannot confirm from source material goes in the **Open questions & gaps log** (Section 12) — never invent a rule to fill a hole.

### Identifier scheme (keep it — cross-references depend on it)

| Prefix | Used for | Section |
|---|---|---|
| `IS-n` / `OS-n` / `UV-n` | In scope / Out of scope / Unverified scope | 2 |
| `PC-n` | Precondition | 3.2 |
| `IN-n` | Input | 3.3 |
| `OU-n` | Output | 3.4 |
| `AS-n` | Assumption | 3.5 |
| `G-nn` | Gap / open question | 12, cited inline everywhere |
| `UC-n` | Unclassified item | 15 |

Cite gaps inline as `[G-07]` wherever the uncertainty actually bites; the converter turns them into gap chips. Every `G-nn` cited inline must exist in Section 12, and vice versa.

---

## A. Writing conventions (read first)

1. **Dual-layer writing.** Each step opens with a one-line plain-language **Goal**, then drops into fully operative detail. The plain line must never be the only description of a decision.

2. **Operative, not code.** Describe *what is done*, not *which function does it*. Name the **system, screen, field, value, and action** — never a code symbol, method, or tool name.
   - ✅ "In FINEOS, open the leave plan and read the **Applicability** field. If it reads *Applicable*, continue; if *Undetermined*, exclude the plan."
   - ❌ "Call `applicability_processing_agent.evaluate()`."
   - For UI actions, be literal: *"open the Leave Request in FINEOS, go to the Certification tab, select the period, click Approve (bottom-right)."*

3. **Every decision is explicit.** Use `IF <condition on a named field/value> THEN <outcome>`. List every branch, including the "otherwise" case. No "etc.", no "and so on".

4. **State the source of every input.** For each value used, say where it comes from, and cite its `IN-n` from §3.3.

5. **Evaluation and writes are separate fields.** `Decision logic` says what is computed. `Actions performed` says what changes outside the working record — system, screen, field, value, button. A step that computes a verdict and writes nothing says so explicitly: *"None external — evaluation only."* Never let a write hide inside a decision sentence.

6. **The chain must interlock.** A step's `Precondition` must be a subset of the previous step's `Postcondition`. Every field in a step's `Output contract` must name the step that consumes it, and every `OU-n` in §3.4 must appear in exactly one step's output contract. This is what lets the judge follow one step's output into the next step's trigger.

7. **One result vocabulary.** Gates produce `PASSED`, `SKIPPED` or `FAILED` (defined in §4.1). Map any source synonym onto these three; do not introduce a fourth.

8. **Document business rules even when they are hidden.** Some rules live in a rules database and are not visible in code. Describe the rule's *intended logic* in full anyway. If the exact logic cannot be confirmed, write the best-known version **and** raise it in the gaps log as `OPAQUE-RULE`.

9. **Always give the "why".** One sentence per step on the business reason. This is what lets a reviewer confirm the rule is *correct*, not merely *present*.

10. **Never assert an absence you did not verify.** Write "None confirmed" plus a gap, not "there is none". This applies especially to human touchpoints, external communications and blocking approval gates.

11. **One vocabulary.** Use the Glossary terms consistently. New term → add it to the Glossary.

---

# SOP REQUIRED SECTIONS

Emit all fifteen, in this order, with these headings.

---

## 1. Document control & metadata

A two-column table, no header row needed.

| Field | Value |
|---|---|
| SOP title | |
| Track | Absence / STD / … |
| Sub-track & phase | |
| Version | e.g. `1` |
| Last updated | YYYY-MM-DD |
| Author | |
| Process / business owner | |
| Status | Draft / In review / Approved |
| Reviewers / sign-off | |
| Review cadence | |

Source documents do **not** go here — they go in Section 14 (Data sources).

---

## 2. Purpose & scope

Open with **What this SOP documents** — 2–4 sentences in plain language: what the process evaluates, against what, and what it produces in the system of record.

Then note that entry paths, preconditions, inputs and outputs are detailed in Section 3 (do not duplicate them here).

Then three tables:

**In scope**

| # | Item | Description |
|---|---|---|
| IS-1 | | |

**Out of scope**

| # | Item | Reason |
|---|---|---|
| OS-1 | | Why it is excluded — no automated path, business exclusion, covered by another SOP |

**Explicitly unclear / unverified scope**

| # | Candidate assertion | Status |
|---|---|---|
| UV-1 | "Quoted assertion carried over from another source that could not be confirmed." | `[G-nn]` what is missing and who can confirm it |

The out-of-scope list is itself a set of evaluable rules — be precise. The unverified table is where inherited claims go when the source material neither confirms nor contradicts them.

---

## 3. Preconditions, Entry Points, Inputs & Outputs

One-line lead, then five numbered subsections **in this order**.

### 3.1 Entry points

| Entry path | Trigger | Enters at | Path-specific behavior |
|---|---|---|---|

One row per path. "Enters at" must say how the entry step is computed, not just name a step (e.g. *"the earliest stage still unsatisfied across the active items"*).

### 3.2 Preconditions

| # | Precondition | Detail | Status |
|---|---|---|---|
| PC-1 | | | Confirmed / Inferred / `[G-nn]` |

### 3.3 Inputs

| # | Input | Source | Consumed at |
|---|---|---|---|
| IN-1 | | System / configuration store | Step n |

### 3.4 Outputs

| # | Output | Destination | Produced at |
|---|---|---|---|
| OU-1 | | System · API or UI | Step n |

### 3.5 Assumptions

| # | Assumption | Note |
|---|---|---|
| AS-1 | | Why it is assumed, and what breaks if it is false |

---

## 4. Glossary & key concepts

| Term / acronym | Meaning |
|---|---|

Include every domain term and system, in plain language. Include any term whose everyday meaning differs from its meaning here (e.g. a step named "manual" that involves no human).

### 4.1 Result vocabulary (standardized)

Emit this table as-is, adjusting only the synonym column to the source material's wording:

| Standard result | Meaning | Synonyms (all equivalent) |
|---|---|---|
| PASSED | The gate is satisfied; processing continues. | |
| SKIPPED | The gate is not actionable; the item is excluded from further automated decisioning at that gate. | |
| FAILED | The gate could not be evaluated or produced an unrecognized state; routed to error handling. | |

Close with a note on how status values are matched (e.g. case-insensitively) and the case they are written in.

---

## 5. Systems & integrations

Four subsections, each a short functional paragraph. No code references.

- **5.1 [System of record]** — what is authoritative, what the process reads, and every category of write. Call out any write performed through a user interface rather than a programmatic interface, and why.
- **5.2 [Rules engine & configuration store]** — what evaluates the rules, where definitions are versioned, which lists/flags live in configuration rather than code.
- **5.3 [Reference data / knowledge base]** — any reference source consulted during evaluation and what it returns.
- **5.4 Observability & error handling** — how runs are monitored, how errors are classified, and what decides whether a failure raises a task or is logged only. Point to Section 8.

---

## 6. Process overview

Three parts, in this order.

**Overview strip** — three one-line values:

| | |
|---|---|
| Trigger | What starts a run |
| Core stages | Stage → Stage → … → Reporting |
| Human steps | None blocking / list the blocking gates |

**End states** — a short list of every way the process can finish, each tagged with a class the renderer colours: `success`, `excluded`, `remediated`, `error`.

**Narrative progression** — six short paragraphs, one per phase, each opening with a bolded phase name. This is the high-level story a non-technical reader follows end to end:

1. **Admission** — how work arrives, what is checked before anything is written, how the entry point is chosen.
2. **Qualification** — the gates that run, in order, what each asks, and what happens to an item that stops qualifying.
3. **Remediation, where it is safe** — which steps can act rather than only judge, and where the line is drawn against acting automatically.
4. **Decision** — how the gate results collapse into one outcome, under what precedence.
5. **Settlement** — what is written back, progressed or recorded so the outcome is real and auditable outside the automation.
6. **Closure** — how every path converges, what the run always produces, and the extent of human involvement.

Keep the six phase names even if a phase is thin; write one sentence saying it is thin.

---

## 7. Step-by-step procedure (the core)

Section 7 renders as two tabs: **Steps**, **Summary**. Emit both parts.


### 7.1 Step blocks

An ordered list of steps. Each step is one decision/action stage. Use the **exact same block, in this field order** — the renderer expects it:

> **Step N — <Step name>**
>
> - **Goal:** one sentence a non-technical reader understands.
> - **Trigger:** what causes this step to run (usually "the previous gate passed at least one item", or an event, or a routing decision).
> - **Precondition (assumed true on entry):** the state this step relies on. Must be a subset of the previous step's postcondition.
> - **Inputs & sources:** each value used + where it comes from, citing `IN-n` from §3.3 and the upstream step that produced it.
> - **Business rule (gate condition):** the rule in result vocabulary — `<value list> → PASSED; <value list> → SKIPPED; otherwise → FAILED`. Include precedence when several conditions can hold at once. If the rule is hidden in a rules database, state its intended logic and tag `OPAQUE-RULE` + gap reference.
> - **Decision logic:** every branch as `IF <condition on named field> THEN <outcome>`, including "otherwise". For steps with narrative sub-stages (2a, 2b, …), use those instead of IF/THEN rows.
> - **Actions performed (side effects / writes):** every write to the system of record, the working record, or the UI, described literally — system, screen, field, value, button. Strictly separate from the evaluation above. Write "None external — evaluation only." when the step changes nothing outside the working record.
> - **Output contract (produces):** a table — each output field, its allowed value set / type, and the downstream step that consumes it. This is what ties one step's output to the next step's trigger.
>   | Field | Allowed values / type | Consumed by |
>   |---|---|---|
> - **Postcondition (guaranteed true on exit):** the state the step guarantees for **every** path that leaves it — pass, skip and stop. Phrase it as one assertion the judge can check.
> - **Outcomes & routing:** each possible result and where it goes next, tagged with a routing class: `go` (continue) · `ok` (success / terminal) · `man` (manual or auto-remediated) · `excl` (excluded) · `err` (error handling).
> - **Stop / exit conditions:** what causes the process to halt here and exactly what is recorded — note name, task name, status, log entry. State explicitly when nothing is written to the system of record.
> - **Human touchpoint:** any task or notification created here, labelled **blocking** or **non-blocking**, cross-referenced to the Summary tab. `None` if the step creates none — but see convention 10 before writing `None` rather than "None confirmed".
> - **Open questions / gaps:** gap references relevant to this step, or `None`.
> - **Why (rationale):** one sentence on the business reason for this step's decision.

Repeat for every step, in execution order. **Keep step numbering stable across versions** (append, don't renumber) so evaluation datasets stay aligned.

Two steps are near-universal and should close every SOP unless the process genuinely lacks them: an **Error & exclusion handling** step (the failure target of every other step, always handing off to reporting) and a **Reporting & audit summary** step (terminal for every path, producing exactly one audit record).

#### When one step routes to several outcomes (single-point bifurcation)

If a *single* step's decision sends the case to different next steps or terminal states but **does not change which steps exist afterwards**, you do NOT need a fork block. Use the ordinary step block: list every branch in **Decision logic** as `IF … THEN …`, map each to its target in **Outcomes & routing**, and gate any later step with **Trigger**. This covers the common case (e.g. *Applicable → Step 3; Not Applicable → skip; no active items → stop*).

#### When the process splits into divergent multi-step paths (true bifurcation)

Use a **fork block** only when a discriminator forks the process into **two or more sub-flows that differ in *which steps exist*** (e.g. *natural birth* runs one set of steps, *C-section* runs a different set), which may later rejoin. This keeps the alternative paths visible instead of interleaving them into a misleading linear list.

> **Step N — <Fork name>  [DECISION]**
>
> - **Goal:** one sentence on what is being decided and why the paths differ.
> - **Trigger:** the precise condition under which the fork is reached.
> - **Precondition (assumed true on entry):** as for any step.
> - **Inputs & sources:** including the discriminator's source.
> - **Discriminator:** the single named field/value that selects the branch (e.g. *delivery type*, read from `<source>`).
> - **Branches:** one row per path — branch key, selecting condition, entry sub-step. Cover every value including "otherwise":
>   - `Branch A — <name>`: `IF <discriminator = value> THEN` enter Step N.A1.
>   - `Branch B — <name>`: `IF <discriminator = value> THEN` enter Step N.B1.
> - **Reconverges at:** `Step M`, or `branches terminate independently — none reconverge`.
> - **Output contract (produces):** at minimum the selected branch key and the discriminator value read.
> - **Postcondition:** exactly one branch has been selected and recorded.
> - **Outcomes & routing:** one entry per branch.
> - **Stop / exit conditions:** what happens when the discriminator is missing or unrecognized.
> - **Human touchpoint / Open questions / Why:** as for any step.

**Branch sub-step numbering.** Sub-steps of a fork at Step N are numbered **`Step N.A1`, `Step N.A2`, …** for Branch A; **`Step N.B1`, `Step N.B2`, …** for Branch B. The letter is the branch, the trailing number is the order within that branch. 

Each sub-step uses the **normal step block plus a `Branch:` field** naming its branch key, and its **Trigger** references the fork outcome (e.g. *"Step 5 selected Branch A (natural birth)"*). The reconvergence step is an ordinary `Step M` whose **Trigger** names the branches that feed it (e.g. *"any branch completed — Step 5.A2 or Step 5.B2"*). Keep fork and sub-step numbering stable across versions.

### 7.2 Summary (three cross-step tables)

These are cross-step views, not new content — every row must reconcile with the step blocks above.

**A · Per-step external system connections** — one row per step, one column per external system:

| Step | [System of record] | [Rules engine] | [UI / browser automation] |
|---|---|---|---|

**B · Manual review checkpoints** — every point a human is brought in:

| Trigger | Task created | Step | Blocking? |
|---|---|---|---|

Follow it with three short notes: whether a **blocking approval gate** exists (or a gap saying none was confirmed — never assert none exists), where **error / exclusion routing** lands, and whether work resolved manually outside the process is expected to **re-enter** it.

**C · External communications** — every outbound communication leaving the organization: email, letter, SMS, portal notification, phone call:

| Step | Communication | Channel | Recipient | When it is sent |
|---|---|---|---|---|

In-system tasks, queue items and forms are **internal** — they belong in tables A and B, not here. Emit a row for **every** step: write `None` where the step sends nothing, `None confirmed` plus a gap where you could not verify. Never omit a step's row.

---

## 8. Error handling & exclusions

A short list covering:

- **Technical / runtime errors** — where they are routed, what is recorded, how they propagate.
- **Business exclusions** — how expected non-processing is distinguished from failure, and where it is recorded.
- **Task creation** — what decides whether a failure raises a task or is logged only, and what the default is.
- **Suppression / incident mode** — any global switch or per-error suppression, and who can set it.
- **Rejected / non-qualifying cases** — where they are recorded and whether anything is written back to the source system. State this explicitly.

Note anything intentionally left to a separate technical document (error catalogs, API patterns) and where that document lives.

---

## 9. Compliance & risk

| Aspect | Status |
|---|---|
| Regulatory mapping | Which obligations apply and how they are evidenced — or a gap |
| Data retention / PII handling | Policy, or a gap |

---

## 10. Operational resilience

| Aspect | Status |
|---|---|
| Retry & backoff on external calls | Confirmed behavior, or a gap |
| Authentication / token handling | |
| Resilience of UI-driven calls | |
| Disaster recovery for a dependency outage | |
| Rollback for a bad rule / configuration deployment | |

---

## 11. End-state catalog

Every terminal outcome and exactly how it is recorded, so each is independently verifiable. Every `stop` and terminal `outcome` in Section 7 must appear here.

| End state | When reached | What is recorded | Operator next action |
|---|---|---|---|

Tag each end state with the same class used in §6 (`success`, `excluded`, `remediated`, `error`) so the renderer colours it consistently.

---

## 12. Open questions & gaps log

A living list of everything that could not be confirmed from source material. This is the deliverable's "spec asks you questions" mechanism — gaps are surfaced, never invented. Each entry is a concrete question to resolve with the client/team.

| Gap | Type | Affects | Question to resolve | Status |
|---|---|---|---|---|
| G-01 | OPAQUE-RULE | Step 2 | What are the exact matching conditions for the classification rule stored in the rules DB (null handling, case sensitivity)? | Open |
| G-02 | MISSING-DETAIL | §3.1, Step 1 | Which upstream system emits the trigger? | Open |

**Types:** `OPAQUE-RULE` (logic hidden in a rules DB) · `MISSING-DETAIL` (source docs don't say) · `AMBIGUITY` (sources conflict) · `ASSUMPTION` (we proceeded on an assumption needing confirmation) · `UNVERIFIED` (inherited claim neither confirmed nor contradicted) · `OUTDATED` (source contradicts current behavior) · `MISSING-ARTIFACT` (a document that should exist does not) · `PRODUCTION-READINESS` (documented but not fully live).

**Affects** uses section (`§3.1`) and/or step (`Step 4`) references. Every gap cited inline in the body must appear here; every gap here should be cited at least once inline, or its affects reference must be precise enough to find.

---

## 13. Change log

| Version | Date | Author | Change |
|---|---|---|---|
| v1 | YYYY-MM-DD | | Initial version — what it established |

Versions are whole numbers (`v1`, `v2`, `v3`). Each row states what changed and why, not just "updates".

---

## 14. Data sources

Every piece of source material this SOP was generated and revised from, and the version it fed into.

| Document | Type | What it contributed | Used in version |
|---|---|---|---|
| `absence_adjudication_playbook.md` | `.md` | Stage sequence, routing logic and gate ordering | v1 |
| `SME_walkthrough_2026-06-03.mp4` | `.mp4` | Evidence-driven entry and the certification write path | v2 |

Include file name, extension, what was actually taken from it, and every SOP version it informed. Close with a note on where the authoritative source register lives, or a gap if none exists.

---

## 15. Appendices

### Appendix A · Unclassified items

A holding place for anything material that does not belong to any section above — one-off constraints, verbal agreements, known workarounds, environment quirks, decisions taken outside the process. Move an item into its proper section as soon as one exists for it.

| # | Item | Detail | Relates to | Raised by / date |
|---|---|---|---|---|
| UC-1 | | | | |

Emit the table even when empty, with a line saying it is empty by design.

---

## B. Worked example (illustrative)

One filled step in the full schema, from the Absence pipeline. *(Illustrative only — exact rule contents must be confirmed against source material; opaque rules are flagged.)*

> **Step 2 — Applicability evaluation, rule evaluation & processing**
>
> - **Goal:** Decide which leave plans on the claim actually apply and should keep moving; set aside the ones that need a human.
> - **Trigger:** Routing set the entry stage to Applicability (Step 1 completed with at least one plan).
> - **Precondition (assumed true on entry):** Customer permitted; claim payload loaded; every plan carries an applicability status and can be tested against the applicability inclusion list.
> - **Inputs & sources:** Active plan list with each plan's current FINEOS applicability status (IN-2); the applicability inclusion list (IN-4); the applicability rule definition (IN-5); knowledge-base provision rules for the customer/plan combination (IN-6); `entry_path` from Step 1.
> - **Business rule (gate condition):** Applicability in [Applicable, N/A] → **PASSED**; any other value → **SKIPPED**. Consolidation of provision verdicts: Undetermined outranks Not Applicable; all provisions pass → Applicable.
> - **Decision logic:**
>   - *2a · Categorization.* **Group A** — on the inclusion list → requires automated rule evaluation. **Group B** — applicability already satisfied and not on the inclusion list → proceeds directly. **Group C** — neither → excluded.
>   - *2b · Automated rule evaluation* (only if Group A is non-empty). Four provision areas are evaluated against the knowledge base, producing a verdict and reasoning per provision, regrouped per plan. "Manual" here names this deeper automated evaluation — **not** a human review.
>   - *2c · Consolidation & override.* For each Group A plan whose verdict differs from its current FINEOS status, applicability is overridden and the payload re-read.
>   - *2d · Final classification.* Confirmed-Applicable plans join the active set; the rest are excluded and referred. Empty active set → business exclusion.
> - **Actions performed (side effects / writes):**
>   - **FINEOS (write):** applicability override submitted per Group A plan whose consolidated verdict differs from its current status — the plan's applicability field is set to the consolidated verdict.
>   - **FINEOS (read):** the claim payload is re-read immediately after the override so the authoritative status, not the intended one, drives the re-check.
>   - **FINEOS (write, conditional):** a `Review Absence` task per plan still not Applicable, carrying the verdict and its reasoning.
>   - **Working record (write):** group assignment, the four provision verdicts with reasoning, and the resulting active plan set.
> - **Output contract (produces):**
>   | Field | Allowed values / type | Consumed by |
>   |---|---|---|
>   | `applicability_result` | PASSED \| SKIPPED (per plan) | Step 3; Step 8 decision precedence |
>   | `applicability_status` | Applicable \| Not Applicable \| Undetermined (written to FINEOS) | Step 2 re-check; audit trail |
>   | `active_plan_set` | List of plans; may be empty | Step 3 |
>   | `provision_verdicts` | 4 verdicts + reasoning text | Review Absence task; Decision Summary |
> - **Postcondition (guaranteed true on exit):** Every plan is categorized and carries an applicability result; FINEOS applicability reflects the consolidated verdict for every Group A plan that needed one; the active plan set contains only plans that are Applicable or N/A. If it is empty, the run has stopped as a business exclusion.
> - **Outcomes & routing:**
>   - `go` Active plans remain → Step 3 · Eligibility
>   - `man` A Group A plan is still not Applicable → "Review Absence" task; the run continues with the remaining plans
>   - `excl` Group C plans, or the combined active set is empty → stop · business exclusion
>   - `err` Override or knowledge-base call fails → Step 11 · Error & exclusion handling
> - **Stop / exit conditions:** **No active plans remain.** A business exclusion is recorded (reason: no applicable leave plan) and handed to Step 11; no decision and no applicability note are written beyond any override already applied. Per-plan non-applicability does *not* stop the run.
> - **Human touchpoint:** **Non-blocking** — `Review Absence` task per plan that stays non-applicable, created *after* the automated decision. See Summary tab → Manual review checkpoints.
> - **Open questions / gaps:** None.
> - **Why (rationale):** Only plans that genuinely apply should consume downstream evaluation, and a plan the automation cannot confirm must reach a human without stalling the run.

### Worked fork example (illustrative)

> **Step 5 — Delivery-type fork  [DECISION]**
>
> - **Goal:** Decide whether the claim follows the natural-birth path or the C-section path, because the two require different evidence and waiting periods.
> - **Trigger:** Step 4 (Certification) confirmed a maternity leave plan is actionable.
> - **Precondition:** A certification record exists for the claim and carries a delivery-type value.
> - **Inputs & sources:** Certification record (IN-2), delivery-type field.
> - **Discriminator:** **Delivery type** (certification record): *Natural birth* or *C-section*.
> - **Branches:**
>   - `Branch A — Natural birth`: `IF Delivery type = "Natural birth" THEN` enter Step 5.A1.
>   - `Branch B — C-section`: `IF Delivery type = "C-section" THEN` enter Step 5.B1.
> - **Reconverges at:** Step 6 (Benefit-period decision).
> - **Output contract (produces):** `branch_selected` (A \| B) → Steps 5.A1 / 5.B1; `delivery_type_read` (the raw value) → audit trail.
> - **Postcondition:** Exactly one branch has been selected and recorded, and the value that selected it is on record.
> - **Outcomes & routing:** `go` Branch A → Step 5.A1 · `go` Branch B → Step 5.B1 · `err` discriminator missing or unrecognized → Step 11.
> - **Stop / exit conditions:** Delivery type absent or unrecognized → error handling; the raw value is recorded with the error.
> - **Human touchpoint:** None.
> - **Open questions / gaps:** confirm the source of record for delivery type `[G-nn]`.
> - **Why (rationale):** The two delivery types carry different statutory recovery periods and evidence rules, so the steps performed genuinely differ.

> **Step 5.A1 — Natural-birth evidence check**
>
> - **Branch:** Branch A — Natural birth.
> - **Goal:** Confirm the standard birth certification is on file.
> - **Trigger:** Step 5 selected Branch A (natural birth).
> - *(… ordinary step block continues, all fields …)*

> **Step 6 — Benefit-period decision**
>
> - **Goal:** Set the approved benefit period for the maternity leave.
> - **Trigger:** Any branch completed — Step 5.A2 or Step 5.B2.
> - *(… ordinary step block continues …)*

---

## C. Definition of Done for an SOP

An SOP is complete when:

- [ ] All **15 sections** are present, in order, with the exact headings and table columns above.
- [ ] Every step uses the full block schema with all fields filled, in the prescribed order (no empty fields — use `None` or `N/A` **with a reason** if truly not applicable).
- [ ] Every decision is written as explicit `IF/THEN` covering all branches including "otherwise".
- [ ] Every step's **Actions performed** contains only writes and side effects; steps that write nothing say so explicitly.
- [ ] Every step's **Output contract** names a consuming step for each field, and every `OU-n` in §3.4 appears in exactly one step's output contract.
- [ ] Every step's **Precondition** is a subset of the previous step's **Postcondition**; the chain interlocks from the first step to the terminal one.
- [ ] Every true bifurcation uses a **fork block** naming a single **Discriminator** and a **Reconverges at** target (or explicit independent termination); every branch has an `IF/THEN` selecting condition; every branch sub-step carries a `Branch:` field and `Step N.<letter><k>` numbering.
- [ ] Every input names its source and cites its `IN-n`; every business rule is described (opaque ones flagged).
- [ ] Every terminal outcome and every stop condition appears in the **End-state catalog** with its recorded artifacts.
- [ ] The three **Summary** tables cover **every** step — including rows that say `None` or `None confirmed`.
- [ ] No absence is asserted without verification — unconfirmed absences are written as "None confirmed" plus a gap.
- [ ] No code symbols, function names, or tool names appear anywhere.
- [ ] A non-technical reader can read the Goals + Section 6 narrative and follow the process end to end.
- [ ] All unknowns are captured in the gaps log as concrete questions — nothing invented.
- [ ] Business + technical reviewer have signed off in Section 1.
