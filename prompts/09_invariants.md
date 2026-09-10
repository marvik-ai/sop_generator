You are extracting **cross-cutting invariants** from a finished SOP — assertions that
hold for the whole run, independent of any single step, in the same spirit as each step's
own Postcondition / Stop-exit-conditions checkpoints (Section 7) but at the level of the
entire process.

Your single most important rule:

> **Derive, don't invent.** Every invariant must restate something the SOP body already
> says (e.g. a stated "no rejection write-back" rule, a stated single-structured-summary-
> per-exit rule, an out-of-scope list, the end-state catalog). Do NOT introduce any rule,
> threshold, or behavior that is not already written in the SOP. If the SOP does not
> support a given invariant, omit it rather than guessing.

## What to look for (use what the SOP actually supports; not all of these may apply)
- A rule about what is or is NOT written back to the system of record on failure/exclusion.
- A rule that every terminal exit produces exactly one structured record/summary.
- The out-of-scope claim shapes/cases that must never be acted on.
- A rule that the terminal outcome always matches one of the documented end states.
- A rule that every error/exclusion is recorded with a reason before the run terminates.

## Output format
Output ONLY a markdown subsection, nothing else (no preamble, no commentary):

```
### Cross-cutting invariants

| Invariant ID | Assertion to verify against the trace | Related gaps |
|---|---|---|
| INV-1 | ... | G-xx or — |
```

- Use IDs `INV-1`, `INV-2`, ... in the order you find them in the SOP.
- Cap the table at 5 rows. If the SOP only supports fewer, output fewer — never pad with
  invented invariants to reach 5.
- "Related gaps" cites an existing `G-xx` ID from the SOP's Section 12 if the invariant
  touches an unconfirmed rule, otherwise `—`.
- Each assertion must be phrased as a single verifiable statement, written the same way
  the SOP's own "Evaluation checkpoints" are phrased.

=== SOP ===
{{SOP}}
=== END SOP ===
