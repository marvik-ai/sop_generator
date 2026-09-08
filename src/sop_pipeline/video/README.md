# Video extraction

An `.mp4` input becomes the same thing every other source becomes: a list of extracted
statements, each with a verbatim `supporting_quote`, a confidence, and a
`supporting_media` timestamp range on the recording's clock. Getting there is two
independent decisions:

1. **Frame extraction** — *which* frames get pulled from the recording.
2. **Analysis** — *how* the picked frames (plus the transcript) get turned into
   statements.

Each is a separate config key, tunable independently of the other:

```yaml
# my_custom_config.yaml, anywhere on disk
frame_extraction: difference   # HOW frames are picked
strategy: sequential           # HOW picked frames become statements
```
```bash
SOP_VIDEO_CONFIG=my_custom_config.yaml uv run sop-pipeline run --inputs inputs/
```

`config.yaml`'s `frame_extraction` key selects the frame-extraction strategy (default
`uniform`) and `strategy` selects the analysis strategy (default `naive`); pointing the
`SOP_VIDEO_CONFIG` env var at a YAML file overrides any subset of either's keys without
editing the checked-in defaults. An unknown value on either axis fails the run rather
than silently falling back.

`pipeline.py` calls only `video.extract()`, `video.cache_key()` and `video.prompt_name()`;
`cache_key()` folds in the analysis strategy's knobs, the active frame-extraction
strategy's name and knobs, and the prompt text — so changing either axis (or editing a
knob) re-extracts instead of mixing statements drawn from two different plans.

## Frame extraction: *which* frames get picked (`frame_extraction.py`)

`VideoProcessor(knobs).extract(path, out_dir)` is the one seam both analysis strategies
use to get frames — neither talks to `media.extract_frames` directly. Two strategies:

### `uniform` — fixed-interval sampling

One frame every `frame_interval_s` seconds, for the whole recording.

Knobs (`config.yaml`, under `uniform:`): `frame_interval_s` (2.0).

### `difference` — keep only frames that noticeably changed

Densely samples every `sample_interval_s` seconds, then keeps a candidate only if its
mean grayscale pixel difference from the immediately preceding *sampled* candidate
exceeds `frame_difference_threshold`. Inspired by (not ported from)
[video-analyzer](https://github.com/byjlw/video-analyzer)'s `frame.py`, with two
deliberate deviations from that reference:

- **The first sampled frame is always kept**, unconditionally. The reference actually
  drops frame 0 unless it happens to score above threshold against a `None` previous
  frame — an edge case of its own scoring guard, not intentional "always keep the first
  frame" behavior worth reproducing.
- **Over-budget thinning is chronological, not score-ranked.** If the kept frames still
  exceed `max_frames`, they're thinned the same evenly-spaced way `uniform` is (below) —
  not the reference's "sort by score, take the top K" — so the end of the procedure is
  never the part silently dropped.

Knobs (`config.yaml`, under `difference:`): `sample_interval_s` (1.0),
`frame_difference_threshold` (10.0).

### Shared: `max_frames` (`config.yaml`, under `shared:`)

Applied centrally by `VideoProcessor` after either strategy runs: if the kept frames
exceed `max_frames`, every Nth frame is kept (not just the first N) so the end of the
procedure isn't dropped. Default `250`. `null` means no cap.

**Caution:** this cap applies before the frames reach `sequential`'s chunking, to the
whole recording's frame list — `sequential`'s "no frame is ever dropped to fit a budget"
guarantee (see below) now depends on this being generous, or `null`, when `sequential` is
selected.

## Analysis: *how* picked frames become statements

### `naive` — everything in one call (`naive.py`, `prompts/02_extract_video.md`)

Transcribe all of the audio, and send **every extracted frame plus the full transcript
in a single multimodal call**.

The model sees the recording as a whole, which is what lets it line up an on-screen change
with the words spoken at that moment and cite both, and catch a fact that only makes sense
across distant moments ("the value he entered at 02:00 is the one rejected at 18:00").

No strategy-specific knobs of its own — frame density/capping is entirely the
frame-extraction axis's job now (`config.yaml`'s `naive:` section is intentionally empty).

### `sequential` — chunks in order, carrying state (`sequential.py`, `prompts/02_extract_video_sequential.md`)

Bucket the extracted frames (and the transcript) into `chunk_s`-second windows **by
timestamp**, and process them **in order**, one LLM call per chunk. Each call is handed
a compact **running state**:

- the **action log** so far — the statements already extracted, one compact line each,
  tail-capped at `state_max_actions`;
- the **last known UI/form state** — where the screen stood at the end of the previous chunk;
- the **open items** — anything still unresolved.

The chunk answers with what it *adds*: new statements, a value it can now read that was
illegible before, an open item it just resolved, and the state to carry forward. Nothing is
restated from scratch, so the prompt stays roughly the same size whether the recording runs
two minutes or forty.

A chunk's frame count is no longer fixed — it depends on what `frame_extraction` produced
for that window (zero, with `difference`, if nothing changed on screen). A window with no
frames but transcript text still gets its LLM call (empty image list); a window with
**neither** frames nor transcript text is skipped.

Knobs (`config.yaml`, under `sequential:`): `chunk_s` (120.0), `state_max_actions` (40),
`chunk_max_tokens` (4000).

`sequential` uses `uniform.frame_interval_s` (default `2.0s`) for its frame density, the
same knob `naive` uses. Raise `uniform.frame_interval_s`, or switch to `difference`
(which throttles frame count to what actually changed on screen), to control frame count
and API cost on long recordings.

## Which to use

**Frame extraction:**

| | `uniform` | `difference` |
|---|---|---|
| Frame density | constant, by time | adapts to how much the screen changes |
| A long static screen | many near-duplicate frames | few or no frames — cheap |
| A frantic sequence of edits | may under-sample fast changes | scales up automatically |
| Predictability | exact frame count, always | count depends on the recording |

**Analysis:**

| | `naive` | `sequential` |
|---|---|---|
| LLM calls per recording | 1 | one per chunk |
| Frames the model sees | subject to the shared `max_frames` cap | same cap applies, but set it generous/`null` here |
| Long recordings | one call gets bigger | prompt size stays roughly constant |
| Cross-recording reasoning | sees everything at once | only what the running state carried |

Short walkthroughs: `naive` + `uniform` is one call and sees everything. Long,
detail-dense screen recordings where a field value matters: `sequential`, with
`max_frames: null`, so no frame is thinned away; pair it with `difference` if the
recording has long static stretches, to keep the chunk count itself down.
`uv run sop-pipeline evaluate` scores any combination against the north star — that is
the way to settle it on real material.

## Shared machinery

| File | What it is |
|---|---|
| `__init__.py` | Config loading + both axes' strategy selection; the only surface the rest of the pipeline sees. |
| `config.yaml` | Checked-in defaults for every strategy's knobs, on both axes. |
| custom config (`SOP_VIDEO_CONFIG`) | Optional, lives anywhere: overrides a subset of `config.yaml`'s keys. |
| `frame_extraction.py` | The frame-extraction axis: `Frame`, `uniform`/`difference`, the shared capping helper, `VideoProcessor`. |
| `media.py` | ffmpeg: sample frames, split audio into ASR-sized chunks, probe a recording's duration. |
| `transcribe.py` | Whisper per audio chunk → one `[mm:ss] text` transcript on the absolute clock. |
| `schema.py` | Pydantic mirrors of what the prompts return (used as Structured Outputs schemas). |

Knobs shared by every strategy, on both axes: `SOP_VIDEO_MODEL`, `SOP_TRANSCRIBE_MODEL`
(both env vars, see `.env.example`), and, under `config.yaml`'s `shared:` section,
`frame_width` (768 — where CUSTOM_SYSTEM field labels stay legible), `audio_chunk_s` (600.0 —
bounds the ASR upload size only, unrelated to `sequential.chunk_s`), and `max_frames`
(see above).

## Adding a strategy

**Adding an analysis strategy:**

1. Write `<name>.py` implementing the contract in `__init__.py`'s docstring:
   `extract(path, knobs) -> list[dict]`, `cache_key(knobs) -> str`, `prompt_name()`.
   `knobs` is the merged `shared:` + the active `frame_extraction` strategy's own
   section + `<name>:`, overlaid with the `SOP_VIDEO_CONFIG` custom config if set —
   get frames via `VideoProcessor(knobs).extract(path, out_dir)`, never
   `media.extract_frames` directly. `cache_key` should be
   `f"{STRATEGY_NAME}:" + json.dumps(knobs, sort_keys=True)` over the full `knobs`
   dict — robust by construction, since it can't forget a field the way a manually
   enumerated key could.
2. Write its prompt in `prompts/`. Every statement it returns must carry
   `supporting_quote` and an absolute `supporting_media` — `gap_audit` reconstructs the
   recording's "source text" from those quotes, so a statement without one is invisible to it.
3. Register the module in `_STRATEGIES` in `__init__.py`.
4. Document it here, and add its knobs (with defaults) to `config.yaml`.

**Adding a frame-extraction strategy:**

1. In `frame_extraction.py`, write `_extract_<name>(path, out_dir, knobs) -> list[Frame]`
   and `_describe_<name>(knobs) -> str` (a short phrase for the `{{FRAME_SAMPLING}}`
   prompt slot). Don't apply `max_frames` capping yourself — `VideoProcessor` does that
   centrally via `_cap_and_thin`, shared by every frame-extraction strategy.
2. Register the pair in `_STRATEGIES` in `frame_extraction.py`.
3. Document it here, and add its knobs (with defaults) to `config.yaml`.
