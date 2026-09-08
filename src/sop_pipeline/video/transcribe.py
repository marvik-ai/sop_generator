"""OpenAI ASR scaffolding: turns a recording's audio chunks into one timestamped transcript.

Each pre-split chunk (`media.extract_audio`) is transcribed separately, then its
chunk-local timestamps are shifted onto the recording's absolute clock so downstream
consumers can quote real times in the file.
"""

from __future__ import annotations

from pathlib import Path

from sop_pipeline import llm


def format_timestamp(seconds: float) -> str:
    """`04:12`, widening to `1:02:03` past the hour (no padded zero hours)."""
    total = max(0, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def transcript(chunks: list[Path], *, chunk_s: float) -> str:
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
