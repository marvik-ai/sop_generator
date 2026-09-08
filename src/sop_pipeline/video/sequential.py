"""The "sequential" video-to-facts strategy: processes chunks in order, carrying a running state.

Each fixed-length chunk gets its own LLM call, handed a compact running state (the action
log so far, the last known UI/form state, and items still open) and returns what that
chunk adds: new statements, a corrected value, or a resolved open item. This keeps the
prompt roughly the same size regardless of recording length. Which frames land in a chunk
is decided upstream by `VideoProcessor` (see `frame_extraction.py`) and then bucketed by
timestamp here — a chunk's frame count depends on what `frame_extraction` produced for
that window. See README.md.
"""

from __future__ import annotations

import json
import logging
import math
import re
import tempfile
from pathlib import Path

from sop_pipeline import llm
from sop_pipeline.prompts import load_prompt, render
from sop_pipeline.video import media, transcribe
from sop_pipeline.video.frame_extraction import Frame, VideoProcessor
from sop_pipeline.video.schema import VideoExtractionChunk
from sop_pipeline.video.transcribe import format_timestamp


logger = logging.getLogger(__name__)

STRATEGY_NAME = "sequential"
PROMPT_NAME = "02_extract_video_sequential.md"

_EMPTY_LOG = "(none — this is the first chunk of the recording)"
_EMPTY_UI_STATE = "(unknown — nothing has been seen yet)"
_EMPTY_OPEN_QUESTIONS = "(none)"

# Inverse of transcribe.format_timestamp: `[04:12]` or `[1:02:03]` at the start of a line.
_TIMESTAMP_RE = re.compile(r"^\[(\d+):(\d{2})(?::(\d{2}))?\]")


def prompt_name() -> str:
    """The prompt file this strategy renders (part of the `video` strategy contract)."""
    return PROMPT_NAME


def cache_key(knobs: dict) -> str:
    """Cache key fragment covering the strategy name and every knob that changes what is
    sent — including the active frame-extraction strategy and its own knobs, folded into
    `knobs` by `video/__init__.py`."""
    return f"{STRATEGY_NAME}:" + json.dumps(knobs, sort_keys=True)


def _line_seconds(line: str) -> float | None:
    """Absolute seconds from a `[mm:ss] text` transcript line, or None if unmarked."""
    match = _TIMESTAMP_RE.match(line)
    if match is None:
        return None
    first, second, third = match.groups()
    if third is None:  # mm:ss
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)


def _transcript_by_chunk(text: str, *, count: int, window_s: float) -> list[list[str]]:
    """Split an absolute-clock transcript into one line list per chunk.

    Each line goes to the chunk its own timestamp falls into, clamped to the last chunk.
    A line with no readable marker joins the chunk of the line before it, since the
    transcript is in order.
    """
    buckets: list[list[str]] = [[] for _ in range(count)]
    current = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        seconds = _line_seconds(line)
        if seconds is not None:
            current = min(int(seconds // window_s), count - 1)
        buckets[current].append(line)
    return buckets


def _frames_by_chunk(
    frames: list[Frame], *, count: int, window_s: float
) -> list[list[Frame]]:
    """Split a chronological frame list into one list per chunk.

    Each frame goes to the chunk its own timestamp falls into, clamped to the last
    chunk — the frame-level mirror of `_transcript_by_chunk`.
    """
    buckets: list[list[Frame]] = [[] for _ in range(count)]
    for frame in frames:
        index = min(int(frame.timestamp_s // window_s), count - 1)
        buckets[index].append(frame)
    return buckets


def _render_action_log(statements: list[dict], *, limit: int) -> str:
    """The action log the next call sees: one compact numbered line per logged statement.

    Each line is numbered by its position in the full log, and only the last `limit`
    entries are shown.
    """
    if not statements:
        return _EMPTY_LOG
    visible = statements[-limit:] if limit > 0 else statements
    first = len(statements) - len(visible) + 1
    lines = []
    if first > 1:
        lines.append(f"(… {first - 1} earlier entries omitted …)")
    for offset, statement in enumerate(visible):
        media_range = str(statement.get("supporting_media", "")).strip() or "??"
        section = str(statement.get("target_section", "")).strip() or "?"
        lines.append(
            f"{first + offset}. [{media_range}] {section}: "
            f"{str(statement.get('statement', '')).strip()}"
        )
    return "\n".join(lines)


def _render_open_questions(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return _EMPTY_OPEN_QUESTIONS
    return "\n".join(f"- {item}" for item in cleaned)


def _parse_chunk(raw: str) -> tuple[list[dict], str | None, list[str] | None]:
    """(statements, ui_state, open_questions) from one chunk response.

    Returns None for a state field when the chunk gave nothing usable for it, so the
    caller keeps the last good value and a bad chunk only costs its own statements.
    """
    try:
        payload = json.loads(raw.strip())
    except json.JSONDecodeError:
        # Fall back to the tolerant array reader for fenced or prose-wrapped output.
        return llm.parse_json_array(raw), None, None
    if not isinstance(payload, dict):
        return [], None, None
    statements = [s for s in payload.get("statements") or [] if isinstance(s, dict)]
    ui_state = str(payload.get("ui_state", "") or "").strip() or None
    raw_questions = payload.get("open_questions")
    open_questions = (
        [str(q) for q in raw_questions] if isinstance(raw_questions, list) else None
    )
    return statements, ui_state, open_questions


def extract(path: Path, knobs: dict) -> list[dict]:
    """Pull the statement list out of one recording, one chunk at a time with running state."""
    window_s = max(1.0, float(knobs["chunk_s"]))
    log_limit = int(knobs["state_max_actions"])
    max_tokens = int(knobs["chunk_max_tokens"])

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        processor = VideoProcessor(knobs)
        frames = processor.extract(path, work / "frames")

        audio_s = float(knobs["audio_chunk_s"])
        text = transcribe.transcript(
            media.extract_audio(path, work / "audio", chunk_s=audio_s),
            chunk_s=audio_s,
        )

        # Chunk count comes from the recording's actual duration
        duration_s = media.probe_duration(path)
        count = max(1, math.ceil(duration_s / window_s))
        frame_chunks = _frames_by_chunk(frames, count=count, window_s=window_s)
        transcript_chunks = _transcript_by_chunk(text, count=count, window_s=window_s)
        duration = format_timestamp(duration_s)
        sampling = processor.describe()
        template = load_prompt(PROMPT_NAME)

        statements: list[dict] = []
        ui_state = _EMPTY_UI_STATE
        open_questions: list[str] = []

        for index in range(count):
            chunk = frame_chunks[index]
            chunk_transcript = "\n".join(transcript_chunks[index])
            if not chunk and not chunk_transcript.strip():
                logger.info(
                    f"chunk {index + 1}/{count}: skipped — no frames, no narration"
                )
                continue

            start_s = index * window_s
            end_s = min(duration_s, start_s + window_s)
            prompt = render(
                template,
                SOURCE_NAME=path.name,
                DURATION=duration,
                CHUNK_INDEX=str(index + 1),
                CHUNK_COUNT=str(count),
                CHUNK_RANGE=(f"{format_timestamp(start_s)}–{format_timestamp(end_s)}"),
                FRAME_COUNT=str(len(chunk)),
                FRAME_SAMPLING=sampling,
                TRANSCRIPT=chunk_transcript or "(no narration in this chunk)",
                ACTION_LOG=_render_action_log(statements, limit=log_limit),
                UI_STATE=ui_state or _EMPTY_UI_STATE,
                OPEN_QUESTIONS=_render_open_questions(open_questions),
            )

            # Each frame is preceded by its own absolute `[mm:ss]` text part, so
            # `supporting_media` can cite the recording's real clock.
            parts: list[dict] = []
            for frame in chunk:
                parts.append({"text": f"[{format_timestamp(frame.timestamp_s)}]"})
                parts.append({"image_path": frame.path})

            raw = llm.complete(
                prompt,
                parts=parts,
                model=llm.video_model(),
                max_tokens=max_tokens,
                temperature=0,
                response_format=VideoExtractionChunk.model_json_schema(),
            )
            found, new_ui_state, new_open_questions = _parse_chunk(raw)
            statements.extend(found)
            if new_ui_state is not None:
                ui_state = new_ui_state
            if new_open_questions is not None:
                open_questions = new_open_questions
            logger.info(
                f"chunk {index + 1}/{count} "
                f"({format_timestamp(start_s)}–{format_timestamp(end_s)}): "
                f"+{len(found)} statements, {len(open_questions)} open"
            )

    return statements
