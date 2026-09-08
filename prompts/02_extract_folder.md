<!-- This is the folder counterpart of prompts/02_extract.md and deliberately repeats its
rules in a multi-source wording — each prompt has to read as one whole instruction. A change
to a shared rule (the `target_section` list, the `decision`-fork rule, the quoting and
hedging rules) belongs in both files. -->

You are extracting structured statements from ONE FOLDER of closely related documents for
later assembly into an SOP (a Standard Operating Procedure). The folder holds several
records of the **same session**: typically a screen recording, a transcript of that
recording, and notes about it. Each extracted statement is one fact relevant to *how a
process works* — its scope, systems, glossary terms, triggers, decision rules, actions,
outcomes, thresholds, and end states. (Note: "extracted statement" here means a unit of
extracted information; it is unrelated to a CUSTOM_SYSTEM claim, which is the case the SOP
documents.)

You are given two things about this folder:
- the **text documents**, each wrapped in its own `<<<SOURCE: name>>> … <<<END SOURCE>>>`
  block;
- the **statements already extracted from the folder's recordings**, as JSON, each carrying
  the recording's name in `source` and the `supporting_media` timestamp range where it was
  observed.

Hard rules:
- **Extract only what these sources actually say.** Do NOT infer, complete, or import
  outside knowledge. If a source is vague, capture it as vague.
- **They are ONE session.** Produce ONE combined statement list for the whole folder, not
  one list per file.
- **Consolidate agreement.** A fact stated by two or three of the sources **with the same
  value** is ONE statement — keep the most specific wording and quote the clearest source. Do
  not emit near-duplicates of the same fact.
- **Never pick a winner, and never consolidate a disagreement.** When the sources give
  **different values** for the same thing (a threshold, a field value, a list, an owner),
  emit **one statement per version**, each with its own `source` and `supporting_quote`, each
  naming the other side in `conflicts_with`.

```json
{"statement": "Rejected claims are routed to the Quality team.",
 "supporting_quote": "anything rejected goes over to Quality",
 "source": "session_a/transcript.md",
 "conflicts_with": "session_a/notes.md says the Intake team"}
{"statement": "Rejected claims are routed to the Intake team.",
 "supporting_quote": "rejections are handled by Intake",
 "source": "session_a/notes.md",
 "conflicts_with": "session_a/transcript.md says the Quality team"}
```

  Preserve both sides; never resolve them, average them, or drop one. **A hedged version is
  still a version**: "I think it's ten days" is a value, not a footnote to somebody else's
  value — give it its own statement with `confidence: low` and the hedge in `notes`. Wording
  differences for the *same* value are not a conflict; consolidate those.
- **The recording is the authority on names, labels and values.** When a transcript or note
  garbles a term the recording shows on screen, use the recording's spelling in `statement`.
  That is normalization, not a conflict.
- **Carry EVERY recording statement through.** The recordings were already extracted; that
  work is not up for review. Each supplied recording statement must appear in your output —
  on its own, or merged with a text fact that states the same thing — with its
  `supporting_media` copied **verbatim**. Never drop one, and never drop one because it looks
  off-topic next to the text documents: if a recording shows something the documents never
  mention, that is exactly the fact worth keeping. Your output can be shorter than the
  inputs only by *merging* duplicates, never by discarding.
- **Attribute every statement, and keep `source` and `supporting_media` consistent.**
  - A fact evidenced by a recording — including one a text document *also* states — is
    attributed to the **recording**: copy `source`, `supporting_media` and
    `supporting_quote` from that recording statement. Never attach a timestamp to a text
    document: nobody can check it there.
  - A fact whose only evidence is text is attributed to that text document, with
    `supporting_media` as `""` — **always**. `supporting_media` is a position in a
    recording, and only a recording statement can supply one. A clock time printed inside a
    text document (a meeting transcript's `[12:07 PM]` speaker stamp, a date, a time of day)
    is **not** `supporting_media`; leave it in the quote and leave the field empty.
  - Use the exact `<<<SOURCE: …>>>` name, or the exact `source` value from a recording
    statement. Never invent a name that is not listed below.
- **Quote your evidence.** Every extracted statement must include a short verbatim
  `supporting_quote` from the source it is attributed to.
- **Flag hedging and uncertainty.** If a source hedges ("I think", "around", "check the tip
  sheet") lower the confidence and note it.
- **Capture forks as `decision` statements.** When the sources say the process *splits into
  divergent paths* based on some value — e.g. "for a natural birth we do X, for a C-section
  we do Y" — record it with `target_section: "decision"`. In the `statement`, name the
  **discriminator** (the field/value that selects the path), the **branch values** it
  produces, and, only if a source says so, **where the branches rejoin**. Do NOT invent
  branches, sub-steps, or a reconvergence point no source states; if the sources only give a
  value difference (e.g. "8 weeks vs 6 weeks") that is an ordinary `step`/`business_rule`,
  not a `decision`.

Map each extracted statement to the SOP section it belongs to. Use one of these `target_section`
values:
`scope`, `glossary`, `systems`, `process_overview`, `step`, `business_rule`,
`error_handling`, `end_state`, `gap`, `decision`.

Return a JSON array. Each element:

```json
{
  "target_section": "step",
  "statement": "Concise, normalized statement of the fact.",
  "supporting_quote": "short verbatim snippet from the source",
  "supporting_media": "04:12–04:31 for a fact observed in a recording, otherwise \"\"",
  "source": "the exact folder-qualified source name the quote came from",
  "confidence": "high | medium | low",
  "conflicts_with": "",
  "notes": "optional: hedging, ambiguity, or a value that may need confirmation"
}
```

=== FOLDER: {{SOURCE_NAME}} ===

=== TEXT DOCUMENTS IN THIS FOLDER ===
{{SOURCE_TEXT}}
=== END TEXT DOCUMENTS ===

=== STATEMENTS ALREADY EXTRACTED FROM THIS FOLDER'S RECORDINGS ===
{{VIDEO_STATEMENTS_JSON}}
=== END RECORDING STATEMENTS ===

=== END FOLDER: {{SOURCE_NAME}} ===

Before you return, check your own output twice:

1. **Count the recordings' statements.** Every statement in the RECORDING STATEMENTS block
   appears in your output — on its own or merged into a text fact it duplicates — carrying its
   `supporting_media` verbatim. So your output holds at least as many non-empty
   `supporting_media` values as that block does. A recording whose subject the documents never
   mention is the case this check exists for: it is still part of this session, and none of its
   facts may be dropped for looking unrelated.
2. **Check every `conflicts_with` you filled in.** The value it refers to must also be present
   as its own statement. If it is not, you dropped a version — add it.

Output ONLY the JSON array — no prose, no code fences.
