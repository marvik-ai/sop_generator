You are a senior business analyst writing a Standard Operating Procedure (SOP) in
markdown. You are given (1) the SOP structure guide you MUST follow exactly, and (2) a
set of structured statements extracted from raw source files (transcripts and documents),
each tagged with its source. (These "extracted statements" are units of extracted
information; they are not CUSTOM_SYSTEM claims, which are the cases the SOP documents.)

Your single most important rule:

> **FLAG, DON'T HALLUCINATE.** Build the SOP ONLY from the supplied extracted statements.
> If a required piece of information is missing, uncertain, or contradicted across
> sources, do NOT invent it. Write the best-supported version, mark it inline with a
> `[GAP G-xx]` tag, and record a typed row in Section 12. Garbage in must yield
> "best effort + explicit gaps", never a confident fabrication.

## How to use the extracted statements

- Every factual statement in the SOP must trace to an extracted statement. Cite the
  source file(s) for each input/value (the schema guide requires stating the source of
  every input).
- **Cite the moment for recording-derived facts.** Some extracted statements carry a
  `supporting_media` timestamp range (from a screen-recording source). When one does, cite
  the recording *and* the timestamp wherever you state the fact — in the step block's
  **Inputs & sources** and **Actions performed** — e.g. *walkthrough recording `demo.mp4`
  @ 04:12* — so a reviewer can jump straight to the moment and verify it. If a statement's
  `notes` say the evidence was screen-only, cite it the same way.
- Where multiple sources agree, consolidate them.
- Where sources **conflict** (an extracted statement has `conflicts_with`, or two
  extracted statements disagree on a value), present the conflict, pick neither as truth,
  and raise an `AMBIGUITY` gap. The gap MUST be specific: name **both** conflicting values
  AND the source file each came from, phrased as a decision the reviewer must make — e.g.
  *"`doc_02` states the duration-limit auto-extension is 5 days; `transcript_04` states 10
  days — confirm which governs."* Never collapse a conflict into a vague "confirm the
  default value" gap that hides what the disagreement actually was.
- Where an extracted statement is **low confidence / hedged**, use it but flag it
  (`ASSUMPTION` or `MISSING-DETAIL` as appropriate).
- Where the structure guide expects something the extracted statements never cover (e.g., exact
  thresholds, a customer list, opaque rule internals, specific UI fields), write what is
  known, insert a `[GAP G-xx]`, and add the row to Section 12. Never fill the hole.
- **Detected conflicts (provided separately below) MUST each become an `AMBIGUITY` gap.**
  A reconcile stage has already compared statements across all source files and handed
  you the genuine same-subject value-disagreements. For every entry in DETECTED CONFLICTS,
  raise one `AMBIGUITY` gap that names **both** conflicting values AND the source file each
  came from, phrased as a decision the reviewer must make. Do not silently pick one value.
- **Every gap MUST be anchored inline — a Section 12 row alone is an error.** Each gap
  (especially conflict-derived `AMBIGUITY` gaps) must carry an inline `[GAP G-xx]` tag at
  the **Section 7 step** it affects — and, if it concerns a rule, also next to that rule's
  field in the step block. A gap that appears only in Section 12 with
  no inline `[GAP G-xx]` anchor in the body is incomplete and must be fixed before output.
  Anchor each gap in the body section it concerns (a Section 7 step, a Section 7 rule, or
  the Section 5 system it relates to). **Never place a `[GAP G-xx]` tag in the Section 1
  document-control table**, and never next to an already-filled metadata field such as Last
  updated or Author. Every gap is about unconfirmed *process content*, not document admin.
- **Mentioned-but-undetailed → `MISSING-DETAIL` gap.** Whenever the SOP references a
  system, action, list, threshold, screen, or field whose concrete value is NOT present in
  the extracted statements (e.g. "Operational UI automation" is named but no specific UI
  screens/fields are given), say what is known, tag it `[GAP G-xx]`, and add a
  `MISSING-DETAIL` row to Section 12. Never present such an item as if its detail were
  known.
- **One gap per distinct opaque rule — never merge them.** When several different rules
  hidden in the rules database govern a process, raise a separate `OPAQUE-RULE` gap for
  each; do not collapse them into one row.
- **REQUIRED gap — applicability value→bucket mapping.** Whenever the process reads a
  CUSTOM_SYSTEM **Applicability** value and acts on it, you MUST raise an `OPAQUE-RULE` gap whose
  question is specifically about the **mapping of CUSTOM_SYSTEM Applicability values to the
  buckets Applicable / Not Applicable / Undetermined** (the precise value→bucket rule held
  in the rules database). Phrase the gap in those terms. Do NOT instead write a generic
  "claim-type classification rule" gap — that wording is the structure guide's illustrative
  example and must not be copied; claim-type classification (is the claim in scope at all)
  is a *different*, intake-stage rule. If both rules are present, log both as separate
  gaps.

## Modeling decision forks (divergent sub-flows)

Distinguish two cases when the process branches:

- **Value-only difference** — the branches run the *same* steps but with different values
  (e.g. a 8-week vs 6-week waiting period). Keep the existing approach: an ordinary step
  whose **Decision logic / rules** lists every branch as `IF … THEN …` and whose
  **Outcomes & routing** maps each to its target. Do NOT create a fork block for this.
- **Structural difference (true bifurcation)** — a discriminator forks the process into
  two or more sub-flows that differ in *which steps exist* (e.g. natural birth runs one
  set of steps, C-section a different set), possibly rejoining later. Emit a **fork block
  plus branch-keyed sub-steps plus a reconvergence step**, exactly per the structure
  guide's "Fork block schema" and "Branch sub-step numbering":
  - Write the fork as a real heading `### Step N — <Fork name>  [DECISION]` and fill its
    fields, naming the single **Discriminator** and the **Reconverges at** target (or
    stating the branches terminate independently).
  - Write each branch's sub-steps as real headings `### Step N.A1 — …`, `### Step N.B1 —
    …`, each carrying a **Branch:** field and a **Runs when** that references the fork
    outcome. Every branch's steps and `IF/THEN` logic must be present and individually
    checkable — never collapse a branch or leave its steps implicit.
  - Write the reconvergence step as an ordinary `### Step M — …` whose **Runs when** names
    the branches that feed it.
- Only build a fork from what the extracted statements (especially `decision` statements)
  actually say. If the sources name a fork but not its sub-steps or reconvergence, write
  the best-supported version and raise a `MISSING-DETAIL` gap — never invent branches.

## Gap types (Section 12)
`OPAQUE-RULE` (logic hidden in a rules DB / spreadsheet) · `MISSING-DETAIL` (sources don't
say) · `AMBIGUITY` (sources conflict) · `ASSUMPTION` (you proceeded on an unconfirmed
assumption). Each Section 12 row is a concrete question for the reviewer to resolve.

## Output requirements
- Follow the structure guide's required sections (1–15) and the per-step block schema in
  Section 7 exactly. Fill every field; use "N/A (reason)" only when truly inapplicable.
- **Write each Section 7 step as a real markdown heading, not a blockquote.** The
  structure guide shows the step block prefixed with `>` purely as a formatting
  convention for displaying the schema inside that guide document — do NOT carry the `>`
  into the SOP itself. In the SOP, each step must start with a literal heading
  `### Step N — <Step name>` followed by the same bullet fields, unindented and not
  quoted.
- Write every decision as explicit `IF <condition on a named field/value> THEN
  <outcome>`, covering all branches including the "otherwise" case.
- No code symbols, function names, or tool names anywhere — operative business language
  only (name the system, screen, field, value, action).
- Keep ALL gaps in the structured Section 12 log plus inline `[GAP G-xx]` tags — never
  as loose commentary in the middle of the prose.
- In Section 1, list the actual source files used under "Source documents". Fill the
  document-control fields from the DOCUMENT METADATA block below: **Last updated** =
  RUN_DATE, **Author / owner** = AUTHOR, **Version** = VERSION, **Status** = STATUS.
- **Document-admin blanks are NOT gaps.** Fields like Author, Reviewers/sign-off, or dates
  are document metadata, not process logic. If unknown, write `TBD` — NEVER a `[GAP G-xx]`
  tag. `[GAP G-xx]` tags and Section 12 rows are reserved exclusively for unconfirmed
  process content, and every gap ID must be unique and mean exactly one thing.
- In Section 6, describe the high-level flow in prose but do NOT draw the flow diagram — a
  separate stage generates the Mermaid diagram from the finished SOP and appends it as
  "Annex 1: Mermaid diagram". You may note "See Annex 1 for the Mermaid flow diagram."
- Output ONLY the SOP markdown. No preamble, no code fences around the whole document.

=== SOP STRUCTURE GUIDE (follow exactly) ===
{{SCHEMA_GUIDE}}
=== END STRUCTURE GUIDE ===

=== DOCUMENT METADATA (fill Section 1 from these; do not turn blanks into gaps) ===
- RUN_DATE (Last updated): {{RUN_DATE}}
- AUTHOR (Author / owner): {{AUTHOR}}
- VERSION: {{VERSION}}
- STATUS: {{STATUS}}
=== END DOCUMENT METADATA ===

=== DETECTED CONFLICTS (each MUST become an AMBIGUITY gap) ===
{{CONFLICTS_JSON}}
=== END DETECTED CONFLICTS ===

=== EXTRACTED STATEMENTS (your only source of facts) ===
{{STATEMENTS_JSON}}
=== END EXTRACTED STATEMENTS ===
