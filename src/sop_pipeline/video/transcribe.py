"""ASR scaffolding: turns a recording into one timestamped transcript.

Two sources feed the same shape (`[mm:ss] text` lines, on the recording's absolute
clock): Whisper over ffmpeg-split audio chunks, or — when audio extraction isn't
allowed in this environment — a same-named `.vtt` file (e.g. an exported Teams meeting
transcript) sitting next to the video.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sop_pipeline import llm
from sop_pipeline.video import media


logger = logging.getLogger(__name__)

# A WebVTT cue timing line, e.g. `00:00:03.320 --> 00:00:11.880`.
_VTT_TIMESTAMP_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})\.(\d+)\s*-->\s*(\d+):(\d{2}):(\d{2})\.(\d+)"
)


def format_timestamp(seconds: float) -> str:
    """`04:12`, widening to `1:02:03` past the hour (no padded zero hours)."""
    total = max(0, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def transcript(
    path: Path, work_dir: Path, *, chunk_s: float, allow_audio_extraction: bool
) -> str:
    """`[mm:ss] text`, one line per segment, on the recording's absolute clock.

    Whisper over ffmpeg-split audio when `allow_audio_extraction` is set, otherwise a
    sibling `.vtt` transcript reformatted to the same shape (see module docstring).
    """
    if not allow_audio_extraction:
        return _transcript_from_vtt(path)
    return _transcript_from_audio(
        media.extract_audio(path, work_dir, chunk_s=chunk_s), chunk_s=chunk_s
    )


def _transcript_from_audio(chunks: list[Path], *, chunk_s: float) -> str:
    """`[mm:ss] text`, one line per ASR segment, on the recording's absolute clock.

    Each chunk's index gives its offset (`index * chunk_s`), since ffmpeg numbered the
    chunks in order and reset each one's clock to zero.
    """
    model = llm.transcribe_model()
    lines: list[str] = []
    for index, chunk in enumerate(chunks):
        offset = index * chunk_s
        for raw in llm.transcribe(chunk, model=model):
            text = str(raw.get("text", "")).strip()
            if text:
                start = float(raw.get("start", 0.0)) + offset
                lines.append(f"[{format_timestamp(start)}] {text}")
    return "\n".join(lines)


def _transcript_from_vtt(video_path: Path) -> str:
    """The sibling `<video>.vtt`, reformatted to `[mm:ss] text` lines.

    A missing sibling only logs a warning and returns an empty transcript — the
    recording still gets processed from its frames alone rather than failing the run.
    """
    vtt_path = video_path.with_suffix(".vtt")
    if not vtt_path.is_file():
        logger.warning(
            f"{video_path.name}: audio extraction is disabled and no companion "
            f"transcript was found at {vtt_path.name}; continuing without narration."
        )
        return ""
    cues = _parse_vtt_cues(vtt_path.read_text(encoding="utf-8"))
    return "\n".join(f"[{format_timestamp(start)}] {text}" for start, text in cues)


def _parse_vtt_cues(raw: str) -> list[tuple[float, str]]:
    """(start_seconds, text) per cue, in file order.

    Splits on blank lines into cue blocks, then finds the timing line in each block —
    everything after it is the cue's text, joined onto one line. This naturally skips
    the `WEBVTT` header block (no timing line) and the optional numeric/UUID cue
    identifier line, which precedes the timing match rather than following it.
    """
    cues: list[tuple[float, str]] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            match = _VTT_TIMESTAMP_RE.match(line)
            if match is None:
                continue
            text = " ".join(lines[index + 1 :])
            if text:
                hours, minutes, seconds, fraction = match.groups()[:4]
                start = (
                    int(hours) * 3600
                    + int(minutes) * 60
                    + int(seconds)
                    + float(f"0.{fraction}")
                )
                cues.append((start, text))
            break
    return cues
