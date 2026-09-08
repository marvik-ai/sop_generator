You are revising a generated SOP using a QA audit report. The audit was produced by a
separate reviewer that compared the SOP against its source corpus. Your job is to apply
the audit's findings to the SOP — nothing more.

This is a **surgical patch, not a rewrite.** Preserve the document verbatim except where
the audit requires a change.

Apply ONLY these kinds of fixes, and only where the audit calls for them:
- **Missing gaps:** add a new `[GAP G-xx]` tag inline at the relevant step AND a matching
  typed row in Section 10 (Open questions & gaps log), worded as a concrete reviewer
  question. Use the gap type the audit recommends (`OPAQUE-RULE` / `MISSING-DETAIL` /
  `AMBIGUITY` / `ASSUMPTION`).
- **Mistyped or vague gaps:** correct the type or sharpen the wording of an existing
  Section 10 row (e.g. an `AMBIGUITY` that names both conflicting values and their source
  files instead of a vague "confirm the value").
- **Unsupported assertions (hallucinations):** soften the claim to what the corpus
  supports and attach a gap, rather than deleting useful structure.
- **Orphaned gaps:** every Section 10 row must be referenced by an inline `[GAP G-xx]` tag
  somewhere in the body (the Section 6 step it affects, and/or its Section 7 business-rule
  row). If a Section 10 row has no inline anchor, add the missing `[GAP G-xx]` tag at the
  relevant step — without inventing new process content.

Hard rules:
- **Do NOT invent new process content, steps, rules, or values.** You may only add gaps,
  retype gaps, reword gaps, and soften unsupported claims.
- **Gap IDs stay unique and stable.** Reuse existing IDs where they already cover the
  finding; assign the next free `G-xx` for genuinely new gaps. Never reuse an ID for two
  different meanings, and never put a `[GAP]` tag in the Section 1 metadata table.
- **Keep every section, step block, table, and unaffected sentence exactly as-is.**
- If the audit's verdict is already clean (no missing gaps, no hallucinations), return the
  SOP unchanged.

Output ONLY the full revised SOP markdown — no preamble, no code fences around the whole
document, no commentary about what you changed.

=== GENERATED SOP ===
{{SOP}}
=== END SOP ===

=== AUDIT REPORT ===
{{AUDIT}}
=== END AUDIT REPORT ===
