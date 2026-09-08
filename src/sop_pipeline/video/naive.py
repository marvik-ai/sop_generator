"""The "naive" video-to-facts strategy: sends every extracted frame plus the full
transcript in one call.

Seeing the whole recording at once lets the model line up an on-screen change with the
words spoken at that moment and cite both. Which frames it sees is decided upstream by
`VideoProcessor` (see `frame_extraction.py`), not by this module.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sop_pipeline import llm
from sop_pipeline.prompts import load_prompt, render
from sop_pipeline.video import media, transcribe
from sop_pipeline.video.frame_extraction import VideoProcessor
from sop_pipeline.video.schema import VideoExtraction
from sop_pipeline.video.transcribe import format_timestamp


STRATEGY_NAME = "naive"
PROMPT_NAME = "02_extract_video.md"


def prompt_name() -> str:
    """The prompt file this strategy renders (part of the `video` strategy contract)."""
    return PROMPT_NAME


def cache_key(knobs: dict) -> str:
    """Cache key fragment covering the strategy name and every knob that changes what is
    sent — including the active frame-extraction strategy and its own knobs, folded into
    `knobs` by `video/__init__.py`."""
    return f"{STRATEGY_NAME}:" + json.dumps(knobs, sort_keys=True)


def extract(path: Path, knobs: dict) -> list[dict]:
    """Pull the statement list out of one recording in a single multimodal call."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        processor = VideoProcessor(knobs)
        frames = processor.extract(path, work / "frames")

        chunk_s = float(knobs["audio_chunk_s"])
        text = transcribe.transcript(
            media.extract_audio(path, work / "audio", chunk_s=chunk_s),
            chunk_s=chunk_s,
        )
        prompt = render(
            load_prompt(PROMPT_NAME),
            SOURCE_NAME=path.name,
            DURATION=format_timestamp(media.probe_duration(path)),
            FRAME_SAMPLING=processor.describe(),
            FRAME_COUNT=str(len(frames)),
            TRANSCRIPT=text,
        )

        # Each frame is preceded by its own `[mm:ss]` text part, so the model can cite a
        # real timestamp in `supporting_media`.
        parts: list[dict] = []
        for frame in frames:
            parts.append({"text": f"[{format_timestamp(frame.timestamp_s)}]"})
            parts.append({"image_path": frame.path})

        # max_tokens=16000: a long walkthrough yields many statements, and a truncated
        # JSON array parses to nothing. Runs inside the temp dir while the JPEGs exist.
        raw = llm.complete(
            prompt,
            parts=parts,
            model=llm.video_model(),
            max_tokens=16000,
            temperature=0,
            response_format=VideoExtraction.model_json_schema(),
        )
    return json.loads(raw)["statements"]
