"""Frame extraction: *which* frames get pulled from a recording, decoupled from how the
picked frames are later turned into statements (that's `naive.py`/`sequential.py`).

`VideoProcessor(knobs).extract(path, out_dir)` is the one seam the analysis strategies
use — neither talks to `media.extract_frames` directly any more. Two strategies:

- `uniform` — one frame every `frame_interval_s` seconds, for the whole recording.
- `difference` — densely samples every `sample_interval_s` seconds, then keeps only a
  frame whose mean grayscale pixel difference from the immediately preceding *sampled*
  frame exceeds `frame_difference_threshold`. Inspired by (not ported from)
  github.com/byjlw/video-analyzer's `frame.py`. Two deliberate deviations from that
  reference, both worth knowing about:
    - the first sampled frame is always kept, unconditionally — the reference actually
      drops frame 0 unless it happens to score above threshold against a `None`
      previous frame, an edge case of its own scoring guard rather than intentional
      "always keep the first frame" behavior.
    - if the kept frames still exceed `max_frames`, they are thinned the same evenly
      spaced way `uniform` is (below), not the reference's score-ranked top-K — so the
      end of the procedure is never the part silently dropped.

Both strategies share one capping step (`_cap_and_thin`, via `max_frames` in `shared:`)
applied centrally by `VideoProcessor`, so budget behavior is identical regardless of
which strategy produced the frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

from sop_pipeline.video import media


@dataclass(frozen=True)
class Frame:
    """One sampled frame, with the recording's real timestamp carried explicitly —
    never recomputed positionally (`index * interval_s`), since frames aren't
    uniformly spaced under every frame-extraction strategy (e.g. `difference`)."""

    path: Path
    timestamp_s: float


# --- uniform: fixed-interval sampling --------------------------------------------


def _extract_uniform(path: Path, out_dir: Path, knobs: dict) -> list[Frame]:
    interval_s = float(knobs["frame_interval_s"])
    paths = media.extract_frames(
        path, out_dir, interval_s=interval_s, width=knobs["frame_width"]
    )
    return [
        Frame(path=frame_path, timestamp_s=index * interval_s)
        for index, frame_path in enumerate(paths)
    ]


def _describe_uniform(knobs: dict) -> str:
    return f"one frame every {float(knobs['frame_interval_s']):.1f}s"


# --- difference: dense-sample, keep only what noticeably changed ----------------


def _mean_difference(current: Image.Image, previous: Image.Image | None) -> float:
    """Mean grayscale pixel difference (0-255) between two `"L"`-mode images.

    `None` for `previous` scores 0.0 — it never triggers a keep on its own; the caller
    force-keeps the first sampled frame instead (see the module docstring).
    """
    if previous is None:
        return 0.0
    histogram = ImageChops.difference(current, previous).histogram()
    total = sum(histogram)
    if total == 0:
        return 0.0
    return sum(value * count for value, count in enumerate(histogram)) / total


def _extract_difference(path: Path, out_dir: Path, knobs: dict) -> list[Frame]:
    sample_interval_s = float(knobs["sample_interval_s"])
    threshold = float(knobs["frame_difference_threshold"])
    candidates = media.extract_frames(
        path, out_dir, interval_s=sample_interval_s, width=knobs["frame_width"]
    )

    kept: list[Frame] = []
    previous: Image.Image | None = None
    for index, candidate in enumerate(candidates):
        with Image.open(candidate) as opened:
            grayscale = opened.convert("L")
            grayscale.load()  # detach from the file before it's reused/closed
        if index == 0 or _mean_difference(grayscale, previous) > threshold:
            kept.append(Frame(path=candidate, timestamp_s=index * sample_interval_s))
        previous = grayscale
    return kept


def _describe_difference(knobs: dict) -> str:
    threshold = float(knobs["frame_difference_threshold"])
    return f"keyframes where the screen changed noticeably (threshold {threshold:.1f})"


_STRATEGIES = {
    "uniform": (_extract_uniform, _describe_uniform),
    "difference": (_extract_difference, _describe_difference),
}


def _cap_and_thin(frames: list[Frame], max_frames: int | None) -> list[Frame]:
    """Evenly thin `frames` down to at most `max_frames`, preserving chronological order
    and the LAST frame — the end of the procedure is never the part dropped. `None`
    skips this step, so no frame is ever dropped — useful for `sequential`, which
    buckets frames by time and can tolerate an uncapped list.
    """
    if max_frames is None:
        return frames
    step = max(1, math.ceil(len(frames) / int(max_frames))) if frames else 1
    return frames[::step]


class VideoProcessor:
    """`VideoProcessor(knobs).extract(path, out_dir)` — the one place both analysis
    strategies get frames from. `knobs` must include `frame_extraction` (the active
    strategy's name), that strategy's own knobs, and `max_frames` (shared, may be
    `None`)."""

    def __init__(self, knobs: dict):
        name = str(knobs["frame_extraction"]).strip()
        strategy = _STRATEGIES.get(name)
        if strategy is None:
            valid = ", ".join(sorted(_STRATEGIES))
            raise RuntimeError(
                f"Unknown frame_extraction strategy {name!r} in config.yaml. "
                f"Valid: {valid}."
            )
        self._extract_fn, self._describe_fn = strategy
        self._knobs = knobs

    def extract(self, path: Path, out_dir: Path) -> list[Frame]:
        frames = self._extract_fn(path, out_dir, self._knobs)
        return _cap_and_thin(frames, self._knobs.get("max_frames"))

    def describe(self) -> str:
        return self._describe_fn(self._knobs)
