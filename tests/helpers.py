"""Fakes shared by the extract-step test modules: a real-but-empty .mp4 on disk and a
stand-in for the whole video package.
"""

from __future__ import annotations

import types
from pathlib import Path

from sop_pipeline import pipeline, video


VIDEO_STATEMENTS = [
    {
        "target_section": "step",
        "statement": "The adjudicator opens the Certification tab.",
        "supporting_quote": "so now I jump into the certification tab",
        "supporting_media": "04:12–04:31",
        "confidence": "high",
        "conflicts_with": "",
        "notes": "",
    }
]

VIDEO_CORPUS = "- [04:12–04:31] so now I jump into the certification tab"


def write_mp4(
    tmp_path: Path, name: str = "demo.mp4", body: bytes = b"\x00fake"
) -> Path:
    """A real file on disk: _video_cache_key hashes the bytes, so it must exist."""
    path = tmp_path / name
    path.write_bytes(body)
    return path


def install_fake_video(monkeypatch, *, statements: list[dict] | None = None):
    """Replace pipeline's module-level `video` name; return the call log."""
    calls: dict = {"extract": 0}

    def extract(path):
        calls["extract"] += 1
        calls["path"] = Path(path)
        return [dict(s) for s in (statements or VIDEO_STATEMENTS)]

    # pipeline talks to the video package through the strategy contract, so the stub has to
    # answer all three calls; the two it doesn't count delegate to the real default strategy.
    fake = types.SimpleNamespace(
        extract=extract, cache_key=video.cache_key, prompt_name=video.prompt_name
    )
    monkeypatch.setattr(pipeline, "video", fake)
    return fake, calls
