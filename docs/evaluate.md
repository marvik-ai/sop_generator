# Stage 3 — `evaluate`

```bash
uv run sop-pipeline evaluate --north-star path/to/sop_north_star.md
```

`--north-star` is required — the trusted SOP is not tracked in this repo (committing
it would leak the answer key), so you must point this at your own copy.

## Plain language

Run this after `run`, on the mock inputs from `generate-mocks`. It asks the model to act
as a grader: compare the SOP the pipeline just generated against the trusted SOP we
started from, and also check it against the answer key of "what each mock file
deliberately left out." It gives two scores —

1. **Did the pipeline figure out the actual process** from messy, incomplete fake
   inputs?
2. **Did it correctly notice what was missing or contradictory**, instead of either
   making something up or staying silent about a real hole?

This stage is for **judging pipeline quality during development** — it requires the
north-star SOP and the coverage manifest, which only exist for the mock test set. It's
not something you'd run against real client output (there's no trusted answer key for
a brand-new real process — that's exactly the gap this pipeline is meant to fill).

## What it produces

`out/evaluation.md` — a markdown report in two parts, plus the same content printed to
the terminal:

1. **Summary (general view)** — the scores and short prose verdicts (see "Part 1" below).
2. **Detailed breakdown (evidence-backed view)** — per-section coverage, a gap-by-gap
   trace, and per-hallucination detail, each backed by verbatim quotes (see "Part 2").

## How it works (technical)

`prompts/05_evaluate_vs_reference.md` is filled with three things and sent to the model
(`SOP_JUDGE_MODEL`, default `gpt-4o`):

- `{{GENERATED}}` — `out/sop_generated.md`, the pipeline's output.
- `{{NORTH_STAR}}` — the file passed via `--north-star`, the trusted answer key.
- `{{MANIFEST}}` — `fixtures/coverage_manifest.md`, the ground truth about what the
  mock inputs deliberately omitted/contradicted (see
  [generate-mocks.md](generate-mocks.md)).

### Part 1 — Summary

A concise top-level view:

- **`## Reconstruction coverage (score/100)`** — of the substantive content in the
  north star (scope, systems, the ordered steps and their decision logic, end states),
  how much did the generated SOP recover? Explicitly told *not* to penalize gaps that
  were correctly flagged because the mock inputs genuinely lacked that information —
  the goal is to reward accurate reconstruction, not punish honesty about limits.
- **`## Gap accuracy (score/100)`** — a short TP/FN/FP feel and a single score (the
  exhaustive per-gap trace lives in Part 2), comparing the generated SOP's Section 12
  (and inline `[GAP G-xx]` tags) against the manifest's "omitted across all inputs" list
  and the deliberate contradiction (the 5-day vs. 10-day duration-limit threshold).
- **`## Hallucinations`** — a 1–3 sentence verdict (per-item detail lives in Part 2).
- **`## Top fixes`** — 3–5 concrete, highest-leverage suggestions for improving the
  prompts.
- **`## Overall`** — one summary line.

### Part 2 — Detailed breakdown

The evidence-backed view, where every assertion is required to carry a **verbatim quote**
from the generated SOP, the north star, or the manifest (no paraphrase, no length cap):

- **`### Coverage by section`** — a table with one row per north-star section 2–9
  (metadata/change-log skipped), marking each `Full`/`Partial`/`Missing` and quoting
  the generated SOP's actual text plus the north-star text wherever they diverge. This
  is what turns the single coverage score into "which sections are weak, and how."
- **`### Gap-by-gap trace`** — a table with one row per manifest ground-truth gap
  (each "omitted across ALL inputs" item + each contradiction), mapping it to the
  matching `G-xx` row in the generated SOP (or `none raised`), a TP/FN/FP verdict, and
  the verbatim quotes from both the SOP and the manifest. False positives (gaps the SOP
  raised that the inputs actually covered) are added as extra rows.
- **`### Hallucination detail`** — for each unsupported statement: the exact quoted SOP
  sentence with its section/step reference, the closest related input file quoted (or
  "no related source"), and a one-line reason it crosses into hallucination.

## How this differs from the gap audit (stage 2d)

It's easy to confuse `evaluate` with the gap audit baked into `run` — they sound
similar but check different things:

| | Gap audit (`prompts/04`, runs inside `run`) | Evaluate (`prompts/05`, this stage) |
|---|---|---|
| Compares the SOP against | The raw input files it was built from | The trusted north-star SOP + the coverage manifest |
| Available for real client data? | Yes — always runs as part of `run` | No — only meaningful for the mock test set |
| Answers | "Is this SOP internally consistent with its own sources?" | "How close did this get to the real, correct process?" |

In short: the gap audit is something you'd keep running in production (it only needs
the inputs you actually have). `evaluate` is a development-time tool for tuning the
prompts before real client transcripts arrive — once they do, there's no north star to
compare against, so this stage's job is finished for that input set.

## Where to make changes

- **Change the scoring criteria or report format:** edit
  `prompts/05_evaluate_vs_reference.md`.
- **If scores are consistently low:** check `out/extraction.json` first (did stage 2b
  actually pull the relevant facts out of the mock files?), then read
  `out/gaps_report.md` (did stage 2d already catch the issue?) before touching this
  prompt — the root cause is more often upstream.
