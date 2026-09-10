You are filtering structured statements extracted from raw SOP source material down to
only those relevant to ONE named SOP, before the remaining statements are reconciled and
synthesized into that SOP.

The target SOP:
{{SOP_IDENTIFIER}}

The extracted statements below may span MULTIPLE distinct processes (e.g. different leave
plans or programs) that happen to live in the same raw inputs. Your one job is to decide,
for each statement, whether it belongs in the target SOP described above.

Hard rules:
- **Keep, don't rewrite.** You are selecting statements, not editing them. You will only
  return indices, never the statement text itself.
- **When uncertain, keep it.** Dropping a statement that actually belongs is worse than
  keeping one that turns out to be irrelevant — a wrongly dropped statement becomes an
  invisible gap downstream, while an extra statement is simply unused. Only drop a
  statement when it clearly concerns a different named process/program than the target
  SOP.
- **Cross-cutting statements stay.** Definitions, systems, glossary entries, or process
  scope statements that plainly apply to the target SOP (even if worded generically) must
  be kept. Only drop a cross-cutting statement if it names a different, specific process.
- **Judge by content, not by source file.** A single source file/recording may cover
  several processes; do not keep or drop a statement just because of which file it came
  from — read the statement text itself.

Each statement below is shown with its 0-based index, its target section, the statement
text, and its source. Return the indices of every statement to KEEP, in ascending order.

=== EXTRACTED STATEMENTS (index, target_section, statement, source) ===
{{STATEMENTS_JSON}}
=== END EXTRACTED STATEMENTS ===

Output ONLY a JSON object: `{"keep_indices": [0, 2, 5, ...]}` — no prose, no code fences.
Return every index if every statement belongs; return an empty array only if truly none
do.
