# Stage 1 — `generate-mocks`

```bash
uv run sop-pipeline generate-mocks --north-star path/to/sop_north_star.md
```

`--north-star` is required

## Plain language

We don't have the client's real meeting transcripts yet. So instead of waiting, we
ask the model to *write* realistic-looking fake transcripts and documents — based on the
SOP we already trust — that imitate what the real inputs will probably look like:
some clean, some messy, some with typos, some where two people say slightly different
things. We deliberately leave some facts out of every file, and write down exactly
what we left out. That "what we left out" list is the answer key we use later to check
whether the real pipeline (stage 2) notices the same holes instead of making things
up.

This stage is for **testing the pipeline**, not for production use. Once real client
transcripts arrive, you skip this stage and drop them straight into `inputs/`.

## What it produces

- `inputs/*.md` — six mock files (four transcripts, two documents). See the table
  below.
- `fixtures/coverage_manifest.md` — the answer key: per file, what it covers, what it
  deliberately omits, and any contradiction baked in on purpose.

## The six mock files

Defined in `src/sop_pipeline/mocks.py` as a list of `MockSpec` objects — one spec per
file. Each spec is **authored by us**, not generated, which is what makes the
coverage manifest trustworthy: we know exactly what each file is supposed to contain
because we wrote the spec, not because we inferred it from the model's output.

| File | What it's testing |
|---|---|
| `transcript_01_clean_overview.md` | The easy case — a clean, fairly complete walkthrough of the whole process. Baseline: the pipeline should reconstruct this well. |
| `transcript_02_noisy_intake.md` | Realistic meeting noise (join chatter, crosstalk, screen-share narration) wrapped around real content about how a claim enters the process. |
| `doc_01_functional_overview.md` | A structured document (not a transcript) — scope tables, in/out-of-scope lists with reasons. |
| `doc_02_rules_sheet_partial.md` | A partial rules reference with some entries explicitly marked "TBD" (opaque rules) and a specific numeric threshold — **5-day** duration-limit extension. |
| `transcript_03_eligibility_spelling.md` | Heavy ASR/transcription errors — system and acronym names get mangled (e.g. AMAZON → "amazonia") the way real auto-transcripts do. |
| `transcript_04_restrictions_contradiction.md` | States the same duration-limit threshold as **10 days** — directly contradicting `doc_02`. This pair exists specifically to test whether stage 2 raises an `AMBIGUITY` gap instead of picking one value silently. |

Across **all** files, several facts are deliberately omitted entirely (the exact pilot
customer list, the precise rules-database value mapping, the exact UI screens used
when there's no API). These are listed in `mocks.GLOBALLY_OMITTED` and must show up as
gaps in the generated SOP — never as invented specifics.

## How a single file gets generated (technical)

For each `MockSpec`, `mocks.generate()`:

1. Loads `prompts/01_generate_mocks.md` as a template.
2. Fills in the spec's fields: filename, kind (transcript/document), the cast of
   speakers (e.g. *"Sandra (American, facilitator) and Ranjit (Indian, principal
   architect)"*), noise level, error level, the `must_include` / `must_omit` fact
   lists, any deliberate contradiction, and extra rendering guidance.
3. Sends the filled prompt to the model (`SOP_SYNTH_MODEL`, default `gpt-4o`)
   along with the **north-star SOP** (the file passed via `--north-star`) as
   background context — the model needs to know the real process to write something
   realistic, but the prompt explicitly tells it not to copy the north star's
   structure or wording.
4. Writes the raw response straight to `inputs/<filename>`.

The realism instructions baked into the prompt (not the Python code) control: MS-Teams
/ Gemini-style timestamp + speaker-line formatting; non-native English speakers
(American, Indian, Argentinean, Uruguayan) with varied phrasing and grammar quirks;
noise that scales with the spec's `noise_level` (join chatter, "you're on mute",
tangents); and transcription errors that scale with `error_level` (mangled system/
acronym names, kept decipherable from context).

After generation, `mocks._render_manifest()` writes `fixtures/coverage_manifest.md`
directly from the specs — it does not re-read or re-analyze the generated files, so
the manifest can't drift from what was actually asked for.

## Where to make changes

- **Add/remove/change a mock file:** edit the `SPECS` list in `mocks.py`.
- **Change how realistic the output looks** (noise style, error style, transcript
  format): edit `prompts/01_generate_mocks.md`.
- **Add a new globally-omitted fact:** add it to `mocks.GLOBALLY_OMITTED` — it will
  automatically appear in the manifest under "Omitted across ALL inputs".
