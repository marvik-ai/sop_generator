"""Integration test: extract() against the real OpenAI API using real input files.

Unlike test_pipeline.py / test_video.py (which monkeypatch llm.complete), this file
makes live calls through sop_pipeline.llm.complete, so it needs a real
OPENAI_API_KEY (see .env.example) and is skipped otherwise. It only covers one
feature end-to-end: turning a list of SourceDoc into a list of extracted statements.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sop_pipeline.ingest import load_corpus
from sop_pipeline.llm import _load_dotenv
from sop_pipeline.pipeline import extract


_INPUTS_DIR = Path(__file__).resolve().parents[1] / "inputs"
_FIXTURES_VIDEOS_DIR = Path(__file__).resolve().parents[0] / "fixtures" / "videos"

_load_dotenv()


def _copy_video(video: Path, dest_dir: Path) -> None:
    """Copy `video` into `dest_dir`, plus its sibling `.vtt` transcript if one exists.

    `allow_audio_extraction` defaults to off, so a recording needs its `.vtt` alongside
    it to be transcribed at all.
    """
    shutil.copy(video, dest_dir / video.name)
    vtt = video.with_suffix(".vtt")
    if vtt.is_file():
        shutil.copy(vtt, dest_dir / vtt.name)


def test_extract_from_a_single_document():
    docs = [
        d for d in load_corpus(_INPUTS_DIR) if d.name == "doc_01_functional_overview.md"
    ]
    assert len(docs) == 1

    statements = extract(docs)
    print(statements)


def test_extract_from_two_documents():
    docs = load_corpus(_INPUTS_DIR)[:2]

    statements = extract(docs)

    print(statements)


def test_extract_from_one_video(tmp_path):
    videos = sorted(_FIXTURES_VIDEOS_DIR.glob("*.mp4"))
    assert len(videos) > 0, "No videos found in fixtures"

    first_video = videos[0]
    _copy_video(first_video, tmp_path)

    docs = load_corpus(tmp_path)

    statements = extract(docs)

    print(statements)


def test_extract_from_one_video_with_the_sequential_strategy(tmp_path, monkeypatch):
    """The chunked, stateful strategy (strategy: sequential) over a real recording.

    A custom config file selects the strategy without touching the developer's checked-in
    config.yaml.
    """
    custom_config = tmp_path / "custom_config.yaml"
    custom_config.write_text(
        "strategy: sequential\nsequential:\n  chunk_s: 30.0\nuniform:\n  frame_interval_s: 5.0\n"
    )
    monkeypatch.setenv("SOP_VIDEO_CONFIG", str(custom_config))

    videos = sorted(_FIXTURES_VIDEOS_DIR.glob("*.mp4"))
    assert len(videos) > 0, "No videos found in fixtures"

    first_video = videos[0]
    _copy_video(first_video, tmp_path)

    docs = load_corpus(tmp_path)

    statements = extract(docs)

    print(statements)


def test_extract_from_one_video_one_text(tmp_path):
    videos = sorted(_FIXTURES_VIDEOS_DIR.glob("*.mp4"))
    assert len(videos) > 0, "No videos found in fixtures"

    first_video = videos[0]
    _copy_video(first_video, tmp_path)

    text_file = _INPUTS_DIR / "doc_01_functional_overview.md"
    assert text_file.exists(), f"Text file not found: {text_file}"
    shutil.copy(text_file, tmp_path / text_file.name)

    docs = load_corpus(tmp_path)

    statements = extract(docs)

    print(statements)


def test_extract_from_a_folder_of_related_documents(tmp_path):
    videos = sorted(_FIXTURES_VIDEOS_DIR.glob("*.mp4"))
    assert len(videos) > 0, "No videos found in fixtures"

    first_video = videos[0]
    session = tmp_path / "session_a"
    session.mkdir()
    _copy_video(first_video, session)
    for name in ("transcript_01_clean_overview.md", "doc_01_functional_overview.md"):
        text_file = _INPUTS_DIR / name
        assert text_file.exists(), f"Text file not found: {text_file}"
        shutil.copy(text_file, session / name)

    docs = load_corpus(tmp_path)
    assert len(docs) == 1
    folder = docs[0]
    assert folder.is_folder() is True
    assert len(folder.members) == 3

    statements = extract(docs)

    print(statements)

    # Every statement is attributed to a real member file, or to the folder as a fallback.
    allowed = {member.name for member in folder.members} | {folder.name}
    assert {s["source"] for s in statements} <= allowed

    # A timestamp only ever sits on a statement attributed to the recording. The transcript
    # carries "[12:07 PM]" speaker stamps of its own and the model does reach for them, so
    # this is the assertion that catches it.
    recording = next(m.name for m in folder.members if m.is_video())
    assert all(
        not s["supporting_media"].strip()
        for s in statements
        if s["source"] != recording
    )


def _mentions(statement: dict, *needles: str) -> bool:
    """True when a statement or its quote contains one of `needles` (hyphens ignored)."""
    haystack = f"{statement['statement']} {statement['supporting_quote']}"
    haystack = haystack.lower().replace("-", " ")
    return any(needle in haystack for needle in needles)


def test_extract_from_a_folder_whose_documents_disagree(tmp_path):
    """Two documents in one folder giving different values -> BOTH versions survive."""
    session = tmp_path / "session_a"
    session.mkdir()
    for name in (
        "doc_02_rules_sheet_partial.md",
        "transcript_04_restrictions_contradiction.md",
    ):
        shutil.copy(_INPUTS_DIR / name, session / name)

    docs = load_corpus(tmp_path)
    assert len(docs) == 1

    statements = extract(docs)

    print(statements)

    five = [s for s in statements if _mentions(s, "5 day", "five day")]
    ten = [s for s in statements if _mentions(s, "10 day", "ten day")]
    assert five, "the rules sheet's 5-day threshold was dropped by the fusion"
    assert ten, "the transcript's ten-day threshold was dropped by the fusion"

    # Each version is attributed to the member that states it, so `reconcile` can name both
    # sides of the conflict downstream.
    assert any(s["source"].endswith("doc_02_rules_sheet_partial.md") for s in five)
    assert any(
        s["source"].endswith("transcript_04_restrictions_contradiction.md") for s in ten
    )
