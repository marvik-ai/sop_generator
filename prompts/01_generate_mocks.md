You are reverse-engineering a realistic INPUT file for a process-documentation
pipeline. The pipeline will later try to reconstruct an SOP from files like yours, so
your job is to produce believable raw source material — NOT a polished SOP.

You are given the finished SOP (the "north star") only as background so you know the
true process. You must NOT reproduce its structure, headings, or wording. Real meeting
transcripts and working documents are messy, partial, and conversational.

=== NORTH STAR SOP (background knowledge only — do not copy its structure) ===
{{NORTH_STAR}}
=== END NORTH STAR ===

## Produce this file

- **Filename:** {{FILENAME}}
- **Kind:** {{KIND}}   (transcript = a meeting transcript; document = a written doc)
- **Profile:** {{PROFILE}}
- **People / authorship:** {{PERSONAS}}
- **Noise level:** {{NOISE_LEVEL}}
- **Spelling / transcription-error level:** {{ERROR_LEVEL}}

### This file MUST convey (in natural, indirect language — never as a tidy list):
{{MUST_INCLUDE}}

### This file MUST NOT mention (these are tested as gaps elsewhere):
{{MUST_OMIT}}

### Deliberate contradiction to embed (if any):
{{CONTRADICTS}}

### Extra guidance:
{{EXTRA}}

## Rules for realism

- **If Kind = transcript:** format like an auto-generated MS-Teams / Gemini transcript —
  timestamps and `Speaker Name: utterance` lines. Everyone speaks ENGLISH, but they are
  NOT all native speakers (American, Indian, Argentinean, Uruguayan) — vary phrasing, filler,
  grammar quirks and idiom accordingly. The substance must be embedded in natural back-
  and-forth and screen-share narration, not stated as bullet points.
- **If Kind = document:** format like a real internal working doc — headings, prose,
  and tables — possibly slightly incomplete (a few "TBD" cells are realistic).
- **Noise** (greetings, "can you see my screen?", "you're on mute", crosstalk, tangents)
  scales with the noise level. High = a lot of it; none = essentially clean.
- **Spelling / transcription errors** scale with the error level. When high, mangle
  system and acronym names the way ASR does (keep them decipherable from context).
- Convey ONLY the facts in the MUST-convey list (plus realistic surrounding chatter).
  Do not leak any MUST-NOT-mention fact, even implicitly.
- Length: realistic for the profile — typically a few hundred to ~1500 words.

## Output

Output ONLY the raw file content (the transcript or the document). No preamble, no
explanation, no code fences.
