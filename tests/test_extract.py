"""Unit tests for the extract step's folder branch: no network, no ffmpeg, no API key.

A subdirectory of the inputs folder is one related document set. These cover the mechanics
of fusing it — one unit, one call, attribution, caching — with the video package and the
OpenAI call both faked (see helpers.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import VIDEO_CORPUS, VIDEO_STATEMENTS, install_fake_video, write_mp4

from sop_pipeline import pipeline
from sop_pipeline.ingest import combined_corpus, load_corpus
from sop_pipeline.prompts import load_prompt


# A stand-in for prompts/02_extract_folder.md: the placeholders are what _extract_folder_one
# fills, so a stub only has to carry those three.
_FOLDER_TEMPLATE = (
    "FOLDER {{SOURCE_NAME}}\n"
    "TEXT\n{{SOURCE_TEXT}}\n"
    "RECORDING STATEMENTS\n{{VIDEO_STATEMENTS_JSON}}\n"
)


def _write_session(tmp_path: Path) -> Path:
    """inputs/ holding one flat doc plus a session folder (recording + transcript + notes)."""
    (tmp_path / "flat.md").write_text("a standalone document", encoding="utf-8")
    session = tmp_path / "session_a"
    session.mkdir()
    write_mp4(session)
    (session / "transcript.md").write_text("the spoken walkthrough", encoding="utf-8")
    (session / "notes.md").write_text("jotted observations", encoding="utf-8")
    return session


def test_load_corpus_folds_a_subdirectory_into_one_doc(tmp_path):
    session = _write_session(tmp_path)
    docs = {doc.name: doc for doc in load_corpus(tmp_path)}

    # One doc for the folder, not one per member — and the flat file is untouched.
    assert set(docs) == {"flat.md", "session_a"}
    assert docs["flat.md"].is_folder() is False

    folder = docs["session_a"]
    assert folder.is_folder() is True
    assert folder.is_video() is False
    assert folder.text == ""
    assert folder.path == session
    assert [m.name for m in folder.members] == [
        "session_a/demo.mp4",
        "session_a/notes.md",
        "session_a/transcript.md",
    ]
    assert [m.is_video() for m in folder.members] == [True, False, False]


def test_load_corpus_skips_a_subdirectory_with_nothing_readable(tmp_path):
    (tmp_path / "flat.md").write_text("body", encoding="utf-8")
    empty = tmp_path / "empty_session"
    empty.mkdir()
    (empty / "clip.mov").write_bytes(b"\x00mov")
    (empty / "blank.md").write_text("  \n", encoding="utf-8")
    (empty / "deeper").mkdir()  # folders are exactly one level deep

    assert [doc.name for doc in load_corpus(tmp_path)] == ["flat.md"]


def test_load_corpus_raises_when_only_an_unreadable_subdirectory_is_present(tmp_path):
    (tmp_path / "empty_session").mkdir()
    (tmp_path / "empty_session" / "clip.mov").write_bytes(b"\x00mov")
    with pytest.raises(ValueError, match="No readable inputs"):
        load_corpus(tmp_path)


def _fake_folder_call(monkeypatch, statements: list[dict]):
    """Capture the rendered folder prompt; return `statements` as the model's answer."""
    captured: dict = {}

    def fake_complete(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["max_tokens"] = kwargs.get("max_tokens")
        return json.dumps({"statements": statements})

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
    return captured


def test_extract_folder_makes_one_call_over_every_text_member(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    calls = {"n": 0}

    def fake_complete(prompt, **_kwargs):
        calls["n"] += 1
        calls["prompt"] = prompt
        return json.dumps({"statements": []})

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
    monkeypatch.setattr(
        pipeline, "_extract_one", lambda *_a: pytest.fail("flat path must not run")
    )

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    pipeline._extract_folder(folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False)

    assert calls["n"] == 1  # one fused call, not one per member
    for expected in (
        "session_a/notes.md",
        "jotted observations",
        "session_a/transcript.md",
        "the spoken walkthrough",
    ):
        assert expected in calls["prompt"]


def test_extract_folder_feeds_video_statements_to_the_folder_prompt(
    monkeypatch, tmp_path
):
    _, video_calls = install_fake_video(monkeypatch)
    captured = _fake_folder_call(monkeypatch, [{"statement": "fused", "source": ""}])

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    statements, cached = pipeline._extract_folder(
        folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False
    )

    assert video_calls["extract"] == 1
    # The recording's statements reach the fused call whole, timestamps included.
    assert "so now I jump into the certification tab" in captured["prompt"]
    assert "04:12–04:31" in captured["prompt"]
    # ...and its evidence lands in the folder's text, which is the gap-audit corpus.
    assert VIDEO_CORPUS in folder.text
    # The fused list comes back as-is.
    assert cached is False
    assert statements == [
        {"statement": "fused", "source": "session_a", "supporting_media": ""},
    ]


def test_extract_folder_keeps_member_attribution_and_rejects_unknown_source(
    monkeypatch, tmp_path
):
    install_fake_video(monkeypatch)
    _fake_folder_call(
        monkeypatch,
        [
            {"statement": "from notes", "source": "session_a/notes.md"},
            {"statement": "from the recording", "source": "session_a/demo.mp4"},
            {"statement": "hallucinated", "source": "nowhere.md"},
            {"statement": "unattributed", "source": ""},
        ],
    )

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    statements, _ = pipeline._extract_folder(
        folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False
    )

    assert [s["source"] for s in statements] == [
        "session_a/notes.md",
        "session_a/demo.mp4",
        "session_a",  # a name that is not a member falls back to the folder
        "session_a",
    ]


def test_extract_routes_a_folder_before_the_video_branch(monkeypatch, tmp_path):
    """A folder whose name ends in .mp4 must still take the folder branch."""
    install_fake_video(monkeypatch)
    _fake_folder_call(monkeypatch, [{"statement": "fused", "source": ""}])
    monkeypatch.setattr(
        pipeline, "_extract_one", lambda *_a: pytest.fail("flat path must not run")
    )

    session = tmp_path / "session.mp4"
    session.mkdir()
    (session / "notes.md").write_text("body", encoding="utf-8")

    statements = pipeline.extract(load_corpus(tmp_path), cache_dir=None)
    assert statements == [
        {"statement": "fused", "source": "session.mp4", "supporting_media": ""}
    ]


def test_extract_folder_cache_hit_skips_the_llm_call(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _write_session(inputs)
    cache_dir = tmp_path / "cache"
    calls = {"n": 0}

    def run_once() -> list[dict]:
        def fake_complete(_prompt, **_kwargs):
            calls["n"] += 1
            return json.dumps({"statements": [{"statement": "fused", "source": ""}]})

        monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
        monkeypatch.setattr(
            pipeline, "_extract_one", lambda *_a: [{"statement": "flat"}]
        )
        folder = next(d for d in load_corpus(inputs) if d.is_folder())
        return pipeline._extract_folder(
            folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", cache_dir, False
        )

    first, first_cached = run_once()
    second, second_cached = run_once()

    assert (first_cached, second_cached) == (False, True)
    fused = [
        {"statement": "fused", "source": "session_a", "supporting_media": ""},
    ]
    assert first == second == fused
    assert calls["n"] == 1
    # The member recording's entry is flattened, so two folders can't collide on it.
    assert (cache_dir / "session_a_demo.mp4.json").is_file()
    assert (cache_dir / "session_a.json").is_file()


def test_extract_folder_cache_misses_when_a_member_changes(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    session = _write_session(tmp_path)
    cache_dir = tmp_path / "cache"
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    folder.text = combined_corpus(folder.members)
    pipeline._write_cache(cache_dir, folder, _FOLDER_TEMPLATE, [{"statement": "x"}])

    (session / "notes.md").write_text("rewritten observations", encoding="utf-8")
    changed = next(d for d in load_corpus(tmp_path) if d.is_folder())
    changed.text = combined_corpus(changed.members)
    assert pipeline._cached_statements(cache_dir, changed, _FOLDER_TEMPLATE) is None


def test_combined_corpus_nests_folder_member_labels(tmp_path):
    """The gap-audit contract: the outer label says one session, the inner ones say which file."""
    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    folder.members = [m for m in folder.members if not m.is_video()]
    folder.text = combined_corpus(folder.members)

    corpus = combined_corpus([folder])
    assert corpus.startswith(
        "<<<SOURCE: session_a>>>\n<<<SOURCE: session_a/notes.md>>>"
    )
    assert "jotted observations" in corpus
    assert "<<<SOURCE: session_a/transcript.md>>>" in corpus
    assert corpus.endswith("<<<END SOURCE>>>\n<<<END SOURCE>>>")


def test_the_real_folder_prompt_has_no_unfilled_placeholders(monkeypatch, tmp_path):
    """Guard against a placeholder typo: `render` leaves an unknown {{TOKEN}} in the prompt."""
    install_fake_video(monkeypatch)
    captured = _fake_folder_call(monkeypatch, [])

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    pipeline._extract_folder(
        folder, load_prompt("02_extract_folder.md"), "VIDEO PROMPT", None, False
    )

    assert "{{" not in captured["prompt"]
    assert captured["max_tokens"] == 16000


def test_extract_folder_clears_a_timestamp_on_a_text_source(monkeypatch, tmp_path):
    """A meeting transcript's own "[12:07 PM]" speaker stamp is not a position in a recording."""
    install_fake_video(monkeypatch)
    _fake_folder_call(
        monkeypatch,
        [
            {
                "statement": "from the transcript",
                "source": "session_a/transcript.md",
                "supporting_media": "12:07–12:08",
            },
            {
                "statement": "from the recording",
                "source": "session_a/demo.mp4",
                "supporting_media": "04:12–04:31",
            },
        ],
    )

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    statements, _ = pipeline._extract_folder(
        folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False
    )

    assert [s["supporting_media"] for s in statements] == ["", "04:12–04:31"]


def test_extract_folder_names_the_recording_in_the_statements_it_passes_on(
    monkeypatch, tmp_path
):
    """The prompt can only attribute a recording fact if the JSON block names the recording."""
    install_fake_video(monkeypatch)
    captured = _fake_folder_call(monkeypatch, [])

    _write_session(tmp_path)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
    pipeline._extract_folder(folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False)

    passed_on = json.loads(captured["prompt"].split("RECORDING STATEMENTS\n")[1])
    assert [s["source"] for s in passed_on] == ["session_a/demo.mp4"]


def test_extract_folder_of_recordings_only_skips_the_fused_call(monkeypatch, tmp_path):
    """With no text member the fused call could only re-emit what it was handed."""
    _, video_calls = install_fake_video(monkeypatch)
    monkeypatch.setattr(
        pipeline.llm, "complete", lambda *_a, **_k: pytest.fail("nothing to fuse with")
    )

    session = tmp_path / "session_a"
    session.mkdir()
    write_mp4(session)
    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())

    statements, cached = pipeline._extract_folder(
        folder, _FOLDER_TEMPLATE, "VIDEO PROMPT", None, False
    )

    assert video_calls["extract"] == 1
    assert cached is False
    assert [s["source"] for s in statements] == ["session_a/demo.mp4"]
    assert statements[0]["supporting_media"] == "04:12–04:31"


def test_extract_folder_cache_misses_when_a_recording_statement_changes(
    monkeypatch, tmp_path
):
    """A recording's quote reaches doc.text; the rest of its statement only reaches the
    fused call — and re-wording it there must still re-extract the folder."""
    _write_session(tmp_path)
    cache_dir = tmp_path / "cache"

    def run(video_statement: dict, video_template: str) -> bool:
        install_fake_video(monkeypatch, statements=[video_statement])
        _fake_folder_call(monkeypatch, [{"statement": "fused", "source": ""}])
        folder = next(d for d in load_corpus(tmp_path) if d.is_folder())
        _, cached = pipeline._extract_folder(
            folder, _FOLDER_TEMPLATE, video_template, cache_dir, False
        )
        return cached

    original = VIDEO_STATEMENTS[0]
    # Same quote and timestamp, different statement: doc.text cannot tell these apart.
    reworded = original | {"statement": "The adjudicator opens Certification first."}
    assert reworded["supporting_quote"] == original["supporting_quote"]

    assert run(original, "VIDEO PROMPT v1") is False
    assert run(original, "VIDEO PROMPT v1") is True
    assert run(reworded, "VIDEO PROMPT v2") is False


def test_load_corpus_warns_about_a_directory_nested_in_a_folder(tmp_path, capsys):
    """A related document set is one level deep, so nested files are dropped — out loud."""
    session = tmp_path / "session_a"
    (session / "recordings").mkdir(parents=True)
    write_mp4(session / "recordings")
    (session / "notes.md").write_text("jotted observations", encoding="utf-8")

    folder = next(d for d in load_corpus(tmp_path) if d.is_folder())

    assert [member.name for member in folder.members] == ["session_a/notes.md"]
    assert "recordings" in capsys.readouterr().out
