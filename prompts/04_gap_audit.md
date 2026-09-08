You are auditing a generated SOP against the raw source corpus it was built from. Your
job is to enforce the "flag, don't hallucinate" principle. You are NOT rewriting the
SOP — you are producing a QA report.

Check three things:

1. **Hallucinations.** Every factual assertion in the SOP must be supported by the
   corpus. List any statement, rule, threshold, value, or field that is NOT supported by
   any source. These are the most serious findings.

2. **Missing gaps.** Anywhere the SOP states something the corpus only hints at, hedges
   on, contradicts, or omits — but which the SOP presents as settled without a
   `[GAP G-xx]` tag — should have been flagged. List each one and the gap type it
   warrants (`OPAQUE-RULE` / `MISSING-DETAIL` / `AMBIGUITY` / `ASSUMPTION`). In
   particular: (a) any value **contradicted** across sources (e.g. a threshold given as
   two different numbers) must be an `AMBIGUITY` gap naming both values and their sources;
   (b) any system, action, list, threshold, screen, or field that the SOP **names but
   leaves without a concrete value** (e.g. "Operational UI automation" with no specific UI
   screens/fields) must be a `MISSING-DETAIL` gap.

3. **Gap quality.** For the gaps that ARE in Section 10: are they concrete, correctly
   typed, and actionable as questions for a reviewer? Note any that are vague or
   mistyped.

Also confirm the structural basics: are all 11 sections present, does every step use the
block schema, is every decision written as IF/THEN, and are there any code/function/tool
names (which are forbidden)?

**Fork integrity (true bifurcations).** If Section 6 contains any fork block (a step
heading ending in `[DECISION]`), check each one: it names a single **Discriminator**; it
names a **Reconverges at** target (a later step) or explicitly states the branches
terminate independently; every branch has an `IF/THEN` selecting condition; every declared
branch has at least one branch-keyed sub-step (`Step N.A1`, `Step N.B1`, …) carrying a
`Branch:` field; every branch either reaches the declared reconvergence step or a terminal
end state in the End-state catalog (no branch dead-ends with no outcome). Flag any fork
that violates these. Conversely, if the corpus describes divergent multi-step paths but the
SOP flattened them into a single interleaved list with no fork block, note that as a
structural finding.

=== GENERATED SOP ===
{{SOP}}
=== END SOP ===

=== SOURCE CORPUS ===
{{CORPUS}}
=== END CORPUS ===

Output a concise markdown report with these headings:
`## Hallucinations (unsupported assertions)`, `## Missing gaps (should have been flagged)`,
`## Gap quality notes`, `## Structural checks`, and a final `## Verdict` line that is
one of: PASS, PASS WITH NOTES, or FAIL — with one sentence of justification.
