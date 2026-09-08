You are grading a generated SOP against a hand-authored north-star SOP (the answer key)
and a coverage manifest (ground truth about what the input set deliberately omitted or
contradicted). The generated SOP was built from messy, partial inputs; the north star
was built from high-quality inputs. Some divergence is expected and correct — the point
is to measure how well the pipeline reconstructs the process AND whether it flagged the
right gaps instead of hallucinating.

Your report has TWO parts: a short **summary** (the general view) followed by a
**detailed breakdown** (the evidence-backed view). Produce both, in this order.

---

# PART 1 — SUMMARY (keep this concise)

Begin this part with the literal heading `## PART 1 — SUMMARY`, then produce exactly the
five sections below, in this order, each as a real markdown heading (a literal `##` line
— do NOT wrap the heading text in backticks or a code span):

## Reconstruction coverage (score/100)
Of the substantive process content in the north star (scope, systems, the ordered steps
and their IF/THEN decision logic, end states), how much did the generated SOP recover
from the poor inputs? Credit correct content; do not penalize for correctly-flagged gaps
where the inputs genuinely lacked the information. **Do not penalize the generated SOP for
omitting north-star content that the coverage manifest says was never in the inputs** —
that is expected, correct divergence, not a coverage miss (see the manifest cross-check
rule in the Coverage-by-section section). 2–4 sentences of justification.

## Gap accuracy (score/100)
Compare the generated SOP's Section 10 (and inline `[GAP G-xx]` tags) against the
manifest's "omitted across ALL inputs" list and per-file contradictions. Give a
true-positive / false-negative / false-positive feel and a single 0–100 score, with a
2–4 sentence justification. (The exhaustive per-gap trace goes in Part 2 — keep this
short.) **This score MUST be consistent with your Part 2 gap-by-gap trace:** count the
`TP` / `FN` / `FP` rows you record there and score from those counts — do not report a
deduction for an item your trace marks `TP`. If all manifest rows are `TP` with no `FP`,
the score is at or near 100; justify any points removed by citing a specific `FN`/`FP`
row from the trace.

## Hallucinations
A 1–3 sentence verdict on whether the SOP asserts anything not supported by the inputs.
(Per-item detail goes in Part 2.)

## Top fixes
The 3–5 highest-leverage prompt/pipeline improvements.

## Overall
One summary line.

---

# PART 2 — DETAILED BREAKDOWN

After the summary, begin this part with the literal heading
`## PART 2 — DETAILED BREAKDOWN`, then output the three subsections below (each a real
`###` heading).
**Rules for this whole part:**
- **Quote, do not paraphrase.** Every cell that references content must contain an exact
  verbatim quote (a sentence or short phrase) from the relevant document, in
  `> quote` or `"quote"` form. If you assert something was reconstructed, missed, or
  invented, prove it with a quote.
- **No length limit.** Favor completeness. It is fine for this part to be several pages.
- Every assertion here must be traceable to an exact quote from one of the three provided
  documents (generated SOP, north star, manifest). If you cannot find a supporting
  quote, say "no supporting text found" rather than inventing one.

### Coverage by section

One row per north-star SOP section, for sections **2 through 9** (skip 1 = metadata and
11 = change log). Use this table:

| Section | Status | Generated SOP excerpt | North-star excerpt (if divergent) |
|---|---|---|---|

- **Section** — e.g. `2. Purpose & scope`, `3. Glossary`, `4. Systems & data sources`,
  `5. Process overview`, `6. Step-by-step procedure`, `7. Business rules reference`,
  `8. Error handling & exclusions`, `9. End-state catalog`.
- **Status** — `Full` / `Partial` / `Missing`.
- **Generated SOP excerpt** — a verbatim quote showing what the generated SOP produced
  for this section (or "—" if Missing).
- **North-star excerpt (if divergent)** — a verbatim quote from the north star ONLY where
  the generated SOP diverged, is weaker, or is missing content; leave "—" if they match.

**Manifest cross-check before assigning Status.** The generated SOP was built only from the
inputs; the north star was built from richer inputs and contains material that was never
available. Before marking a section `Partial`/`Missing` because the north star has more,
check the coverage manifest. If the extra north-star content is something the manifest lists
as deliberately omitted, not present in any input, or a system/repository/term named only in
the north star (e.g. a document repository the inputs never mention), it is **expected
divergence**: keep the Status `Full`, put the north-star-only item in the North-star excerpt
column, and append the note "north-star-only (out of input scope)". Reserve `Partial`/
`Missing` for content the inputs *did* provide but the generated SOP failed to reconstruct.

### Gap-by-gap trace

=== PRE-VERIFIED MANIFEST VERDICTS (deterministic — do not override) ===
{{PRE_VERIFIED}}
=== END PRE-VERIFIED ===

The table above was produced by a deterministic Python script using literal substring
matching. For MF-01, MF-03, and MF-04: copy the Matched Gap ID and Verdict values from
that table exactly as-is into your output table below — do not re-evaluate them. For
MF-02: apply the manifest matching rule yourself (the Python check does not cover it).

The manifest's "Omitted across ALL inputs" section has stable-ID items (`MF-01`..`MF-04`),
each with a matching rule. Your gap-by-gap trace must reproduce the pre-verified verdicts
for MF-01/MF-03/MF-04 unchanged and apply the MF-02 rule yourself. This is what keeps
gap-accuracy scoring stable across runs.

**MF-02 — worked positive case (do not under-credit).** A Section 10 gap (or its inline
`[GAP G-xx]` anchor / Section 7 rule row) asking for the exact mapping or conditions of the
**Applicability field/value in the rules database** — or, equivalently, how CUSTOM_SYSTEM
Applicability values map to the buckets *Applicable / Not Applicable / Undetermined* —
**satisfies MF-02 → TP**. Example wording that IS a TP: *"What are the exact mapping
conditions for the Applicability field in the rules database?"* Mark MF-02 `FN` **only** if
no such gap exists, or the only related gap is about generic claim-type / in-scope
**intake** classification (a different, intake-stage rule). Do not return `FN` while quoting
a gap that matches the rule above — if you can quote it, it is a TP.

One row per `MF-xx`, in order, using this table:

| Manifest ID | Type | Manifest item | Matching rule | Matched Gap ID | Verdict | Generated SOP quote |
|---|---|---|---|---|---|---|

- **Manifest ID** — `MF-01` / `MF-02` / `MF-03` / `MF-04` (copy as given).
- **Type** — copy the manifest's `Type` column for that row.
- **Manifest item** — copy the manifest's `Manifest item` column for that row.
- **Matching rule** — copy the manifest's `Matching rule` column for that row verbatim (so
  your verdict is auditable against the literal rule you applied).
- **Matched Gap ID** — see algorithm step 4 above.
- **Verdict** — `TP` or `FN`, derived from algorithm step 4. Do not mark `TP` based on
  topical proximity alone; the rule's literal conditions must hold (e.g. for `MF-02`, a
  generic "claim-type classification rule" gap does NOT satisfy the rule and must be `FN`
  even though it is topically related).
- **Generated SOP quote** — verbatim text of the matched or closest row (fill this in
  before deciding the Verdict, per the algorithm above).

After the four `MF-xx` rows, add additional rows for **FP**: any generated `G-xx` Section
10 row whose underlying fact the inputs actually DID provide (i.e. it shouldn't have been
flagged as a gap at all). Mark these `Manifest ID` as `—` and `Verdict` as `FP`.

### Hallucination detail

For EACH statement in the generated SOP that is not supported by the inputs (cross-check
against the manifest — content unique to the north star but absent from the inputs must
NOT appear as fact in the generated SOP), give:

- **Generated SOP statement** — the exact quoted sentence, with its section/step
  reference (e.g. "Section 6, Step 3").
- **Closest related source** — name the closest related input the SOP might have leaned
  on and quote it, OR write "no related source" if it appears wholly invented.
- **Why unsupported** — one line on why this crosses from reasonable-inference into
  hallucination (e.g. "north-star-only fact never present in any input").

If there are no hallucinations, write "None found." and briefly note the riskiest
borderline inference you considered.

---

=== GENERATED SOP ===
{{GENERATED}}
=== END GENERATED SOP ===

=== NORTH-STAR SOP (answer key) ===
{{NORTH_STAR}}
=== END NORTH-STAR SOP ===

=== COVERAGE MANIFEST (ground truth) ===
{{MANIFEST}}
=== END MANIFEST ===
