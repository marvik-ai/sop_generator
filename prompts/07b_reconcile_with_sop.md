## Overlay: reconciling against an existing SOP

An existing SOP is supplied below (EXISTING SOP). It is being revised with new material,
so treat its confidently-stated content as an additional source alongside the extracted
statements — not as ground truth to defer to.

- **A same-subject value disagreement is a conflict**, exactly as between two extracted
  statements: if the existing SOP confidently asserts one value and an extracted statement
  gives a different value for the same subject, emit a conflict object in the same shape as
  above, with `"source": "existing SOP"` on the SOP's side and `"suggested_gap_type":
  "AMBIGUITY"`.
- **Not a conflict: a gap the SOP itself already flagged.** If the existing SOP marks the
  subject unresolved — an inline `[GAP G-xx]` tag, a row in its gaps log, or a
  `TBD`/placeholder value — a new statement that supplies a value is a **resolution**, not
  a disagreement. Do not emit a conflict for it.
  - Example: the SOP says "the auto-extension threshold is `[GAP G-04]`" and a new
    transcript states "the auto-extension threshold is 10 days" — this is a resolution, not
    a conflict. Emit nothing.
  - Example: the SOP confidently states "the auto-extension threshold is 5 days" (no gap
    tag) and a new transcript states "10 days" — this IS a conflict.

Output is still ONLY the JSON array of conflicts described above — no prose, no code
fences, `[]` if there are no genuine conflicts.

=== EXISTING SOP ===
{{EXISTING_SOP}}
=== END EXISTING SOP ===
