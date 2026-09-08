"""Unit tests for the video branch: no network, no ffmpeg, no API key.

Every subprocess call is a fake that writes the artifact it was asked for by parsing
argv (the `mermaid` pattern in test_pipeline.py), and every OpenAI call is monkeypatched
on the `llm` module the caller holds.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
from helpers import VIDEO_CORPUS, VIDEO_STATEMENTS, install_fake_video, write_mp4
from PIL import Image

from sop_pipeline import pipeline, video
from sop_pipeline.ingest import SourceDoc, load_corpus
from sop_pipeline.prompts import load_prompt
from sop_pipeline.video import frame_extraction, media, naive, sequential, transcribe
from sop_pipeline.video.frame_extraction import Frame, VideoProcessor
from sop_pipeline.video.transcribe import format_timestamp


_NAIVE_KNOBS = {
    "frame_extraction": "uniform",
    "frame_interval_s": 2.0,
    "max_frames": 250,
    "frame_width": 768,
    "audio_chunk_s": 600.0,
}

_SEQUENTIAL_KNOBS = {
    "frame_extraction": "uniform",
    "frame_interval_s": 2.0,
    "max_frames": 250,
    "chunk_s": 120.0,
    "frame_width": 768,
    "audio_chunk_s": 600.0,
    "state_max_actions": 40,
    "chunk_max_tokens": 4000,
}


# --- helpers -------------------------------------------------------------------


def _fake_ffmpeg(
    captured: dict, *, frames: int = 0, chunks: int = 0, returncode: int = 0
):
    """subprocess.run replacement that writes the artifacts named in argv."""

    def fake_run(argv, **_kwargs):
        captured["argv"] = list(argv)
        target = Path(argv[-1])
        for index in range(1, frames + 1):
            (target.parent / f"frame_{index:05d}.jpg").write_bytes(b"jpg")
        for index in range(chunks):
            (target.parent / f"audio_{index:05d}.m4a").write_bytes(b"m4a")
        return types.SimpleNamespace(returncode=returncode, stdout="", stderr="boom")

    return fake_run


def _stub_decode(
    monkeypatch,
    *,
    frames: int,
    transcript: str = "",
    interval_s: float = 2.0,
    duration_s: float | None = None,
):
    """Drive naive.extract without ffmpeg or a real VideoProcessor: `frames` fake frames
    on an `interval_s`-second grid, and a fixed transcript."""
    frame_list = [
        Frame(path=Path(f"/frames/frame_{i:05d}.jpg"), timestamp_s=(i - 1) * interval_s)
        for i in range(1, frames + 1)
    ]
    monkeypatch.setattr(
        naive.VideoProcessor, "extract", lambda self, path, out_dir: frame_list
    )
    monkeypatch.setattr(
        naive.VideoProcessor,
        "describe",
        lambda self: f"one frame every {interval_s:.1f}s",
    )
    monkeypatch.setattr(naive.media, "extract_audio", lambda *_a, **_kw: [])
    monkeypatch.setattr(
        naive.media,
        "probe_duration",
        lambda *_a, **_kw: (
            duration_s if duration_s is not None else frames * interval_s
        ),
    )
    monkeypatch.setattr(naive.transcribe, "transcript", lambda *_a, **_kw: transcript)

    captured: dict = {}

    def fake_complete(prompt, *, parts=None, model, **_kwargs):
        captured["prompt"] = prompt
        captured["parts"] = parts
        captured["model"] = model
        return json.dumps(
            {"statements": [{"target_section": "step", "statement": "x"}]}
        )

    monkeypatch.setattr(naive.llm, "complete", fake_complete)
    return captured


# --- format_timestamp ----------------------------------------------------------


def test_format_timestamp_sub_minute():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(42.4) == "00:42"


def test_format_timestamp_minutes():
    assert format_timestamp(252.0) == "04:12"


def test_format_timestamp_past_an_hour():
    assert format_timestamp(3723.0) == "1:02:03"


# --- _ffmpeg_command -----------------------------------------------------------


def test_ffmpeg_command_returns_the_bundled_binary(monkeypatch):
    monkeypatch.setattr(media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/wheel/ffmpeg")
    assert media._ffmpeg_command() == ["/wheel/ffmpeg"]


def test_ffmpeg_command_none_when_the_wheel_has_no_binary(monkeypatch):
    def _raise():
        raise RuntimeError("no binary for this platform")

    monkeypatch.setattr(media.imageio_ffmpeg, "get_ffmpeg_exe", _raise)
    assert media._ffmpeg_command() is None


# --- extract_frames ------------------------------------------------------------


def test_extract_frames_returns_the_written_frames_in_order(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    captured: dict = {}
    monkeypatch.setattr(media.subprocess, "run", _fake_ffmpeg(captured, frames=3))

    frames = media.extract_frames(
        write_mp4(tmp_path), tmp_path / "frames", interval_s=2.0, width=768
    )

    assert [f.name for f in frames] == [
        "frame_00001.jpg",
        "frame_00002.jpg",
        "frame_00003.jpg",
    ]
    assert all(f.is_file() for f in frames)

    argv = captured["argv"]
    assert argv[argv.index("-vf") + 1] == "fps=1/2.0,scale=768:-2"
    assert argv[argv.index("-q:v") + 1] == "4"
    assert argv[-1].endswith("frame_%05d.jpg")


def test_extract_frames_purges_stale_frames_first(monkeypatch, tmp_path):
    # A caller may reuse the output directory across runs: a leftover from a longer
    # previous recording must not be handed a timestamp it never had.
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    monkeypatch.setattr(media.subprocess, "run", _fake_ffmpeg({}, frames=2))

    out_dir = tmp_path / "frames"
    out_dir.mkdir()
    stale = out_dir / "frame_00099.jpg"
    stale.write_bytes(b"old")

    frames = media.extract_frames(
        write_mp4(tmp_path), out_dir, interval_s=2.0, width=768
    )
    assert [f.name for f in frames] == ["frame_00001.jpg", "frame_00002.jpg"]
    assert not stale.exists()


def test_extract_frames_raises_when_ffmpeg_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "_ffmpeg_command", lambda: None)
    with pytest.raises(RuntimeError, match="uv sync"):
        media.extract_frames(
            write_mp4(tmp_path), tmp_path / "frames", interval_s=2.0, width=768
        )


def test_extract_frames_raises_when_ffmpeg_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    monkeypatch.setattr(media.subprocess, "run", _fake_ffmpeg({}, returncode=1))
    with pytest.raises(RuntimeError, match="failed to extract frames"):
        media.extract_frames(
            write_mp4(tmp_path), tmp_path / "frames", interval_s=2.0, width=768
        )


# --- extract_audio -------------------------------------------------------------


def test_extract_audio_returns_the_chunks_in_order(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    captured: dict = {}
    monkeypatch.setattr(media.subprocess, "run", _fake_ffmpeg(captured, chunks=3))

    chunks = media.extract_audio(write_mp4(tmp_path), tmp_path / "audio", chunk_s=600.0)
    assert [c.name for c in chunks] == [
        "audio_00000.m4a",
        "audio_00001.m4a",
        "audio_00002.m4a",
    ]

    # Only the flags that carry meaning — the argv also has -hide_banner/-nostdin/-y.
    argv = captured["argv"]
    assert "-vn" in argv
    assert argv[argv.index("-ac") + 1] == "1"
    assert argv[argv.index("-ar") + 1] == "16000"
    assert argv[argv.index("-c:a") + 1] == "aac"
    assert argv[argv.index("-f") + 1] == "segment"
    assert argv[argv.index("-segment_time") + 1] == "600.0"
    assert argv[argv.index("-reset_timestamps") + 1] == "1"
    assert argv[-1].endswith("audio_%05d.m4a")


def test_extract_audio_purges_stale_chunks_first(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    monkeypatch.setattr(media.subprocess, "run", _fake_ffmpeg({}, chunks=1))

    out_dir = tmp_path / "audio"
    out_dir.mkdir()
    stale = out_dir / "audio_00007.m4a"
    stale.write_bytes(b"old")

    chunks = media.extract_audio(write_mp4(tmp_path), out_dir, chunk_s=600.0)
    assert [c.name for c in chunks] == ["audio_00000.m4a"]
    assert not stale.exists()


# --- probe_duration --------------------------------------------------------------


def test_probe_duration_parses_the_ffmpeg_stderr_duration_line(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    captured: dict = {}

    def fake_run(argv, **_kwargs):
        captured["argv"] = list(argv)
        return types.SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="  Duration: 00:04:12.34, start: 0.000000, bitrate: 500 kb/s\n",
        )

    monkeypatch.setattr(media.subprocess, "run", fake_run)

    assert media.probe_duration(write_mp4(tmp_path)) == pytest.approx(252.34)
    # No output file is written, so ffmpeg needs an explicit null target to actually
    # decode (and reliably flush the Duration line) instead of exiting early.
    assert captured["argv"][-3:] == ["-f", "null", "-"]


def test_probe_duration_raises_without_a_duration_line(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/usr/bin/ffmpeg"
    )
    monkeypatch.setattr(
        media.subprocess,
        "run",
        lambda argv, **_kwargs: types.SimpleNamespace(
            returncode=1, stdout="", stderr="ffmpeg has no idea what this file is"
        ),
    )
    with pytest.raises(RuntimeError, match="did not report a duration"):
        media.probe_duration(write_mp4(tmp_path))


def test_probe_duration_raises_when_ffmpeg_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "_ffmpeg_command", lambda: None)
    with pytest.raises(RuntimeError, match="uv sync"):
        media.probe_duration(write_mp4(tmp_path))


# --- transcript offsetting -----------------------------------------------------


def test_segments_are_shifted_onto_the_recordings_clock(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transcribe.llm,
        "transcribe",
        lambda path, *, model: [
            {"start": 5.0, "end": 9.0, "text": f"line from {path.name}"},
            {"start": 12.0, "end": 14.0, "text": ""},  # dropped: no text
        ],
    )

    chunks = [tmp_path / "audio_00000.m4a", tmp_path / "audio_00001.m4a"]
    lines = transcribe.transcript(chunks, chunk_s=600.0).splitlines()

    assert lines[0] == "[00:05] line from audio_00000.m4a"
    # Chunk 2's local [00:05] must read as [10:05] on the recording's clock.
    assert lines[1] == "[10:05] line from audio_00001.m4a"
    assert len(lines) == 2


# --- frame_extraction: uniform ---------------------------------------------------


def test_uniform_extract_builds_frames_on_the_interval_grid(monkeypatch, tmp_path):
    paths = [tmp_path / f"frame_{i:05d}.jpg" for i in range(1, 4)]
    monkeypatch.setattr(
        frame_extraction.media, "extract_frames", lambda *_a, **_kw: list(paths)
    )
    knobs = {"frame_interval_s": 2.0, "frame_width": 768}

    frames = frame_extraction._extract_uniform(Path("demo.mp4"), tmp_path, knobs)

    assert [f.timestamp_s for f in frames] == [0.0, 2.0, 4.0]
    assert [f.path for f in frames] == paths


def test_uniform_describe():
    assert (
        frame_extraction._describe_uniform({"frame_interval_s": 2.0})
        == "one frame every 2.0s"
    )


# --- frame_extraction: difference -------------------------------------------------


def test_mean_difference_is_zero_for_identical_images():
    a = Image.new("L", (4, 4), color=100)
    b = Image.new("L", (4, 4), color=100)
    assert frame_extraction._mean_difference(a, b) == 0.0


def test_mean_difference_scores_a_pixel_change():
    a = Image.new("L", (4, 4), color=0)
    b = Image.new("L", (4, 4), color=50)
    assert frame_extraction._mean_difference(a, b) == pytest.approx(50.0)


def test_mean_difference_with_no_previous_is_zero():
    assert frame_extraction._mean_difference(Image.new("L", (4, 4), 200), None) == 0.0


def test_difference_extract_always_keeps_the_first_frame_and_thresholds_the_rest(
    monkeypatch, tmp_path
):
    # candidate 0: kept unconditionally (first frame), regardless of score.
    # candidate 1: barely different from 0 (diff 5 < threshold 10) -> dropped.
    # candidate 2: very different from 1 (diff 95 > threshold) -> kept.
    # candidate 3: identical to 2 (diff 0) -> dropped.
    colors = [0, 5, 100, 100]
    paths = []
    for index, color in enumerate(colors):
        path = tmp_path / f"candidate_{index}.jpg"
        Image.new("RGB", (4, 4), color=(color, color, color)).save(path, format="JPEG")
        paths.append(path)
    monkeypatch.setattr(
        frame_extraction.media, "extract_frames", lambda *_a, **_kw: list(paths)
    )
    knobs = {
        "sample_interval_s": 0.5,
        "frame_width": 768,
        "frame_difference_threshold": 10.0,
    }

    frames = frame_extraction._extract_difference(Path("demo.mp4"), tmp_path, knobs)

    assert [f.path for f in frames] == [paths[0], paths[2]]
    assert [f.timestamp_s for f in frames] == [0.0, 1.0]


def test_difference_describe():
    text = frame_extraction._describe_difference({"frame_difference_threshold": 10.0})
    assert text == "keyframes where the screen changed noticeably (threshold 10.0)"


# --- frame_extraction: _cap_and_thin ----------------------------------------------


def _frames(count: int) -> list[Frame]:
    return [
        Frame(path=Path(f"/frames/frame_{i:05d}.jpg"), timestamp_s=float(i))
        for i in range(count)
    ]


def test_cap_and_thin_keeps_every_nth_frame_and_the_tail():
    thinned = frame_extraction._cap_and_thin(_frames(600), 200)
    assert len(thinned) == 200
    assert thinned[0].timestamp_s == 0.0
    assert thinned[-1].timestamp_s == 597.0  # the tail of the recording is kept


def test_cap_and_thin_passes_through_under_budget():
    frames = _frames(30)
    assert frame_extraction._cap_and_thin(frames, 250) == frames


def test_cap_and_thin_with_none_max_frames_is_a_noop():
    frames = _frames(600)
    assert frame_extraction._cap_and_thin(frames, None) == frames


# --- frame_extraction: VideoProcessor ---------------------------------------------


def test_video_processor_dispatches_and_applies_the_shared_cap(monkeypatch):
    monkeypatch.setitem(
        frame_extraction._STRATEGIES,
        "uniform",
        (lambda path, out_dir, knobs: _frames(10), lambda knobs: "stub sampling"),
    )
    processor = VideoProcessor({"frame_extraction": "uniform", "max_frames": 4})

    frames = processor.extract(Path("demo.mp4"), Path("/out"))

    assert len(frames) == 4


def test_video_processor_describe_delegates_to_the_active_strategy():
    processor = VideoProcessor({"frame_extraction": "uniform", "frame_interval_s": 2.0})
    assert processor.describe() == "one frame every 2.0s"


def test_video_processor_raises_on_an_unknown_frame_extraction_name():
    with pytest.raises(RuntimeError, match="difference, uniform"):
        VideoProcessor({"frame_extraction": "bogus"})


# --- naive.extract -------------------------------------------------------------


def test_video_prompt_renders_every_token(monkeypatch, tmp_path):
    captured = _stub_decode(
        monkeypatch,
        frames=126,
        transcript="[00:04] so now I jump into the certification tab",
    )

    statements = naive.extract(tmp_path / "demo.mp4", _NAIVE_KNOBS)

    prompt = captured["prompt"]
    assert "{{" not in prompt  # every placeholder substituted
    assert "demo.mp4" in prompt
    assert "04:12" in prompt  # DURATION: probed as 126 frames x 2.0s
    assert "126 frames — one frame every 2.0s" in prompt  # FRAME_COUNT + FRAME_SAMPLING
    assert "[00:04] so now I jump into the certification tab" in prompt  # TRANSCRIPT

    # Each frame is preceded by its own timestamp text part, which is what lets the model
    # attribute an observation to a real moment.
    assert captured["parts"][:4] == [
        {"text": "[00:00]"},
        {"image_path": Path("/frames/frame_00001.jpg")},
        {"text": "[00:02]"},
        {"image_path": Path("/frames/frame_00002.jpg")},
    ]
    assert statements == [{"target_section": "step", "statement": "x"}]


def test_naive_uses_whatever_frames_video_processor_hands_it(monkeypatch, tmp_path):
    # Capping/thinning now lives entirely in VideoProcessor/_cap_and_thin (see the
    # frame_extraction tests below) — naive.extract must not re-derive or re-thin
    # anything itself, just consume the given list as-is, at whatever count.
    captured = _stub_decode(monkeypatch, frames=17, interval_s=6.0)

    naive.extract(tmp_path / "demo.mp4", _NAIVE_KNOBS)

    images = [p["image_path"] for p in captured["parts"] if "image_path" in p]
    assert len(images) == 17
    assert "17 frames — one frame every 6.0s" in captured["prompt"]


def test_naive_wires_the_difference_frame_extraction_strategy_end_to_end(
    monkeypatch, tmp_path
):
    """Unlike the tests above (which stub VideoProcessor.extract itself), this drives the
    real VideoProcessor + real _extract_difference through naive.extract, so a break in
    how the two modules are wired together would show up here."""
    colors = [0, 5, 100, 100]  # same fixture as test_difference_extract_...: keeps 0, 2
    candidates = []
    for index, color in enumerate(colors):
        path = tmp_path / f"candidate_{index}.jpg"
        Image.new("RGB", (4, 4), color=(color, color, color)).save(path, format="JPEG")
        candidates.append(path)
    monkeypatch.setattr(
        frame_extraction.media, "extract_frames", lambda *_a, **_kw: list(candidates)
    )
    monkeypatch.setattr(naive.media, "extract_audio", lambda *_a, **_kw: [])
    monkeypatch.setattr(naive.media, "probe_duration", lambda *_a, **_kw: 2.0)
    monkeypatch.setattr(naive.transcribe, "transcript", lambda *_a, **_kw: "")

    captured: dict = {}

    def fake_complete(prompt, *, parts=None, model, **_kwargs):
        captured["prompt"] = prompt
        captured["parts"] = parts
        return json.dumps({"statements": []})

    monkeypatch.setattr(naive.llm, "complete", fake_complete)

    knobs = {
        "frame_extraction": "difference",
        "sample_interval_s": 0.5,
        "frame_difference_threshold": 10.0,
        "max_frames": None,
        "frame_width": 768,
        "audio_chunk_s": 600.0,
    }

    naive.extract(tmp_path / "demo.mp4", knobs)

    images = [p["image_path"] for p in captured["parts"] if "image_path" in p]
    prompt = captured["prompt"]
    assert images == [candidates[0], candidates[2]]
    assert "2 frames — keyframes where the screen changed noticeably" in prompt


# --- custom config override -----------------------------------------------------


def test_config_is_unchanged_when_the_env_var_is_unset(monkeypatch):
    monkeypatch.delenv("SOP_VIDEO_CONFIG", raising=False)
    assert video._config()["strategy"] == "naive"


def test_env_var_points_to_a_custom_config_that_overrides_a_key(monkeypatch, tmp_path):
    custom_file = tmp_path / "my_custom.yaml"
    custom_file.write_text("strategy: sequential\nshared:\n  frame_width: 512\n")
    monkeypatch.setenv("SOP_VIDEO_CONFIG", str(custom_file))
    config = video._config()
    assert config["strategy"] == "sequential"
    assert config["shared"]["frame_width"] == 512
    # Unset keys are untouched, i.e. this is a merge, not a replace.
    assert config["shared"]["audio_chunk_s"] == 600.0
    assert config["shared"]["max_frames"] == 250
    assert config["frame_extraction"] == "uniform"
    assert config["naive"] == {}


def test_env_var_pointing_to_a_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("SOP_VIDEO_CONFIG", str(tmp_path / "does_not_exist.yaml"))
    with pytest.raises(RuntimeError, match="SOP_VIDEO_CONFIG"):
        video._config()


# --- strategy selection --------------------------------------------------------


def _config_with_strategy(name: str) -> dict:
    """A full video config with `strategy` overridden, built from the real defaults."""
    config = video._config()
    config["strategy"] = name
    return config


def test_naive_is_the_default_strategy():
    assert video.strategy_name() == "naive"
    assert video._strategy() is naive
    assert video.prompt_name() == "02_extract_video.md"


def test_config_selects_the_sequential_strategy(monkeypatch):
    config = _config_with_strategy("sequential")
    monkeypatch.setattr(video, "_config", lambda: config)
    assert video._strategy() is sequential
    assert video.prompt_name() == "02_extract_video_sequential.md"
    assert video.cache_key().startswith("sequential:")


def test_an_unknown_strategy_raises_and_names_the_valid_ones(monkeypatch):
    # A typo must not quietly cost a full extraction run against the wrong strategy.
    config = _config_with_strategy("sequencial")
    monkeypatch.setattr(video, "_config", lambda: config)
    with pytest.raises(RuntimeError, match="naive, sequential"):
        video.extract(Path("demo.mp4"))


def test_an_unknown_frame_extraction_raises_and_names_the_valid_ones(monkeypatch):
    config = video._config()
    config["frame_extraction"] = "diffs"
    monkeypatch.setattr(video, "_config", lambda: config)
    with pytest.raises(RuntimeError, match="difference, uniform"):
        video.extract(Path("demo.mp4"))


def test_config_selects_the_difference_frame_extraction_strategy(monkeypatch):
    config = video._config()
    config["frame_extraction"] = "difference"
    monkeypatch.setattr(video, "_config", lambda: config)
    assert video.frame_extraction_name() == "difference"
    _, knobs = video._active()
    assert knobs["frame_extraction"] == "difference"
    assert "frame_difference_threshold" in knobs


def test_active_merges_shared_frame_extraction_and_strategy_knobs():
    strategy, knobs = video._active()
    assert strategy is naive
    assert knobs["frame_extraction"] == "uniform"
    assert knobs["frame_interval_s"] == 2.0  # from uniform:
    assert knobs["max_frames"] == 250  # from shared:
    assert knobs["audio_chunk_s"] == 600.0  # from shared:


def test_active_tolerates_an_analysis_section_with_nothing_under_it(monkeypatch):
    # A YAML section with no children (naive: {}) can also come back as None rather
    # than {} depending on how it's written — _active() must not choke either way.
    config = video._config()
    config["naive"] = None
    monkeypatch.setattr(video, "_config", lambda: config)
    strategy, knobs = video._active()
    assert strategy is naive
    assert knobs["frame_extraction"] == "uniform"


def test_the_selected_strategy_is_resolved_per_call(monkeypatch):
    # Bound at import time this would be frozen, and switching strategy mid-process (or
    # after config.yaml is read) would silently keep running the old one.
    sequential_config = _config_with_strategy("sequential")
    monkeypatch.setattr(video, "_config", lambda: sequential_config)
    assert video._strategy() is sequential
    naive_config = _config_with_strategy("naive")
    monkeypatch.setattr(video, "_config", lambda: naive_config)
    assert video._strategy() is naive


def test_every_strategy_satisfies_the_contract():
    config = video._config()
    frame_name = str(config["frame_extraction"]).strip()
    for name, strategy in video._STRATEGIES.items():
        knobs = {
            **(config.get("shared") or {}),
            **(config.get(frame_name) or {}),
            **(config.get(name) or {}),
            "frame_extraction": frame_name,
        }
        assert callable(strategy.extract)
        assert isinstance(strategy.cache_key(knobs), str)
        # The prompt file must exist, or the run dies at the first recording.
        assert load_prompt(strategy.prompt_name())


def test_every_frame_strategy_satisfies_the_contract():
    config = video._config()
    for name, (extract_fn, describe_fn) in frame_extraction._STRATEGIES.items():
        knobs = {
            **(config.get("shared") or {}),
            **(config.get(name) or {}),
            "frame_extraction": name,
        }
        assert callable(extract_fn)
        assert isinstance(describe_fn(knobs), str)


# --- sequential: transcript windowing ------------------------------------------


def test_transcript_lines_land_in_the_chunk_they_belong_to():
    text = "\n".join(
        [
            "[00:05] first chunk",
            "[01:59] still the first chunk",
            "[02:00] second chunk",
            "[1:00:00] way past the end, clamped to the last chunk",
        ]
    )
    buckets = sequential._transcript_by_chunk(text, count=2, window_s=120.0)
    assert buckets[0] == ["[00:05] first chunk", "[01:59] still the first chunk"]
    assert buckets[1] == [
        "[02:00] second chunk",
        "[1:00:00] way past the end, clamped to the last chunk",
    ]


def test_an_unmarked_transcript_line_sticks_to_the_previous_chunk():
    # Losing narration is worse than misfiling it by a chunk.
    text = "[02:00] second chunk\ncontinued with no marker"
    buckets = sequential._transcript_by_chunk(text, count=2, window_s=120.0)
    assert buckets[0] == []
    assert buckets[1] == ["[02:00] second chunk", "continued with no marker"]


def test_line_seconds_inverts_format_timestamp():
    for seconds in (0, 42, 252, 3723):
        assert sequential._line_seconds(f"[{format_timestamp(seconds)}] x") == seconds
    assert sequential._line_seconds("no marker here") is None


# --- sequential: the running state ---------------------------------------------


def test_the_action_log_is_tail_capped_and_numbered_over_the_full_log():
    statements = [
        {
            "target_section": "step",
            "statement": f"step {i}",
            "supporting_media": "00:01",
        }
        for i in range(5)
    ]
    rendered = sequential._render_action_log(statements, limit=2)
    assert "3 earlier entries omitted" in rendered
    # Numbered by position in the FULL log, so the model can refer to an entry.
    assert "4. [00:01] step: step 3" in rendered
    assert "5. [00:01] step: step 4" in rendered
    assert "step 0" not in rendered


def test_an_empty_state_says_so_rather_than_rendering_blank():
    # A blank token would leave the model guessing whether state was withheld.
    assert "first chunk" in sequential._render_action_log([], limit=40)
    assert sequential._render_open_questions([]) == "(none)"
    assert sequential._render_open_questions(["a", "  ", "b"]) == "- a\n- b"


# --- sequential.extract --------------------------------------------------------


def _stub_sequential(
    monkeypatch,
    *,
    frames: int,
    transcript: str = "",
    replies=None,
    interval_s: float = 6.0,
    duration_s: float | None = None,
):
    """Drive sequential.extract without ffmpeg or a real VideoProcessor; return the
    per-chunk call log. `interval_s` defaults to 6.0s (the old sequential-only default of
    chunk_s/chunk_frames = 120/20) purely so the existing chunk-shape assertions below
    keep their original meaning — sequential itself no longer controls this, it's just a
    convenient fake frame density for these tests."""
    frame_list = [
        Frame(path=Path(f"/frames/frame_{i:05d}.jpg"), timestamp_s=(i - 1) * interval_s)
        for i in range(1, frames + 1)
    ]
    monkeypatch.setattr(
        sequential.VideoProcessor, "extract", lambda self, path, out_dir: frame_list
    )
    monkeypatch.setattr(
        sequential.VideoProcessor,
        "describe",
        lambda self: f"one frame every {interval_s:.1f}s",
    )
    monkeypatch.setattr(sequential.media, "extract_audio", lambda *_a, **_kw: [])
    monkeypatch.setattr(
        sequential.media,
        "probe_duration",
        lambda *_a, **_kw: (
            duration_s if duration_s is not None else frames * interval_s
        ),
    )
    monkeypatch.setattr(
        sequential.transcribe, "transcript", lambda *_a, **_kw: transcript
    )

    calls: list[dict] = []

    def fake_complete(prompt, *, parts=None, model, **_kwargs):
        calls.append({"prompt": prompt, "parts": parts, "model": model})
        if replies is not None:
            return replies[min(len(calls) - 1, len(replies) - 1)]
        index = len(calls)
        return json.dumps(
            {
                "statements": [
                    {
                        "target_section": "step",
                        "statement": f"chunk {index} step",
                        "supporting_quote": "q",
                        "supporting_media": "00:01",
                        "confidence": "high",
                        "conflicts_with": "",
                        "notes": "",
                    }
                ],
                "ui_state": f"screen after chunk {index}",
                "open_questions": [f"open after chunk {index}"],
                "resolved": [],
            }
        )

    monkeypatch.setattr(sequential.llm, "complete", fake_complete)
    return calls


def test_sequential_makes_one_call_per_chunk_and_keeps_every_frame(
    monkeypatch, tmp_path
):
    # 50 frames on a 6.0s grid span 300s -> 3 chunks of 120s, the last one short.
    # Nothing is thinned or capped: the point of chunking is that no frame is dropped to
    # fit a budget.
    calls = _stub_sequential(monkeypatch, frames=50)

    statements = sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    assert len(calls) == 3
    images = [
        [p["image_path"] for p in call["parts"] if "image_path" in p] for call in calls
    ]
    assert [len(i) for i in images] == [20, 20, 10]
    assert images[0][0].name == "frame_00001.jpg"
    assert images[-1][-1].name == "frame_00050.jpg"  # the tail of the recording is kept
    assert len(statements) == 3


def test_sequential_frame_markers_are_absolute_not_chunk_local(monkeypatch, tmp_path):
    calls = _stub_sequential(monkeypatch, frames=50)

    sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    markers = [[p["text"] for p in call["parts"] if "text" in p] for call in calls]
    # 120s / 20 frames = one frame every 6s.
    assert markers[0][:2] == ["[00:00]", "[00:06]"]
    # Chunk 2 must NOT restart at 00:00 — supporting_media would be wrong by two minutes.
    assert markers[1][0] == "[02:00]"
    assert markers[2][0] == "[04:00]"


def test_the_running_state_reaches_the_next_call(monkeypatch, tmp_path):
    calls = _stub_sequential(monkeypatch, frames=40)

    sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    first, second = calls[0]["prompt"], calls[1]["prompt"]
    # Chunk 1 is told the state is empty; chunk 2 is told what chunk 1 found.
    assert "first chunk of the recording" in first
    assert "chunk 1 step" in second
    assert "screen after chunk 1" in second
    assert "open after chunk 1" in second
    assert "chunk 1 step" not in first


def test_sequential_prompt_renders_every_token(monkeypatch, tmp_path):
    calls = _stub_sequential(
        monkeypatch,
        frames=40,
        # A phrase the prompt body itself never uses, so the windowing assertions below
        # can't pass on the prompt's own example.
        transcript="[02:04] and here I paste the reference number into the search box",
    )

    sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    for index, call in enumerate(calls):
        assert "{{" not in call["prompt"]  # every placeholder substituted
        assert "demo.mp4" in call["prompt"]
        assert f"**{index + 1} of 2**" in call["prompt"]
    assert "04:00" in calls[0]["prompt"]  # DURATION: 40 frames x 6.0s
    # The transcript is windowed: that line is in chunk 2 only.
    assert "reference number into the search box" in calls[1]["prompt"]
    assert "reference number into the search box" not in calls[0]["prompt"]
    assert "(no narration in this chunk)" in calls[0]["prompt"]


def test_a_chunk_that_returns_garbage_does_not_lose_the_run(monkeypatch, tmp_path):
    first = json.dumps(
        {
            "statements": [{"target_section": "step", "statement": "kept"}],
            "ui_state": "screen after chunk 1",
            "open_questions": ["still open"],
            "resolved": [],
        }
    )
    calls = _stub_sequential(monkeypatch, frames=60, replies=[first, "I refuse", "{}"])

    statements = sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    # The bad chunk contributes nothing but does not derail the run...
    assert len(calls) == 3
    assert statements == [{"target_section": "step", "statement": "kept"}]
    # ...and it must not wipe the state either: a malformed response silently closing every
    # unresolved question would turn a parse failure into a lost gap.
    assert "screen after chunk 1" in calls[2]["prompt"]
    assert "still open" in calls[2]["prompt"]


def test_sequential_cache_key_covers_every_knob():
    before = sequential.cache_key({**_SEQUENTIAL_KNOBS, "state_max_actions": 40})
    after = sequential.cache_key({**_SEQUENTIAL_KNOBS, "state_max_actions": 41})
    assert before != after


def test_sequential_cache_key_changes_when_frame_extraction_name_changes():
    # Switching frame_extraction must invalidate the cache even if, by coincidence,
    # every knob VALUE happened to match the other strategy's.
    uniform = sequential.cache_key({**_SEQUENTIAL_KNOBS, "frame_extraction": "uniform"})
    difference = sequential.cache_key(
        {**_SEQUENTIAL_KNOBS, "frame_extraction": "difference"}
    )
    assert uniform != difference


def test_naive_cache_key_changes_when_frame_extraction_name_changes():
    uniform = naive.cache_key({**_NAIVE_KNOBS, "frame_extraction": "uniform"})
    difference = naive.cache_key({**_NAIVE_KNOBS, "frame_extraction": "difference"})
    assert uniform != difference


def test_sequential_calls_a_chunk_with_narration_but_no_frames(monkeypatch, tmp_path):
    # duration 480s / chunk_s 120s = 4 windows: [0,120) has a frame; [120,240) has NO
    # frames but has narration -> must still get an LLM call, empty image list;
    # [240,360) has neither -> skipped entirely; [360,480) has a frame.
    frame_list = [
        Frame(path=Path("/frames/frame_00001.jpg"), timestamp_s=0.0),
        Frame(path=Path("/frames/frame_00002.jpg"), timestamp_s=400.0),
    ]
    monkeypatch.setattr(
        sequential.VideoProcessor, "extract", lambda self, path, out_dir: frame_list
    )
    monkeypatch.setattr(
        sequential.VideoProcessor, "describe", lambda self: "stub sampling"
    )
    monkeypatch.setattr(sequential.media, "extract_audio", lambda *_a, **_kw: [])
    monkeypatch.setattr(sequential.media, "probe_duration", lambda *_a, **_kw: 480.0)
    monkeypatch.setattr(
        sequential.transcribe,
        "transcript",
        lambda *_a, **_kw: "[02:30] a spoken-only fact with nothing on screen",
    )

    calls: list[dict] = []

    def fake_complete(prompt, *, parts=None, model, **_kwargs):
        calls.append({"prompt": prompt, "parts": parts})
        return json.dumps(
            {"statements": [], "ui_state": "", "open_questions": [], "resolved": []}
        )

    monkeypatch.setattr(sequential.llm, "complete", fake_complete)

    sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    assert len(calls) == 3  # window [240,360) skipped: no frames AND no narration
    assert calls[1]["parts"] == []  # window [120,240): transcript-only, zero frames
    assert "0 frames — stub sampling" in calls[1]["prompt"]
    assert "a spoken-only fact" in calls[1]["prompt"]


def test_sequential_chunk_count_follows_probed_duration_not_frame_count(
    monkeypatch, tmp_path
):
    # Only 1 frame total, but a long probed duration must still drive the chunk count.
    frame_list = [Frame(path=Path("/frames/frame_00001.jpg"), timestamp_s=0.0)]
    monkeypatch.setattr(
        sequential.VideoProcessor, "extract", lambda self, path, out_dir: frame_list
    )
    monkeypatch.setattr(
        sequential.VideoProcessor, "describe", lambda self: "stub sampling"
    )
    monkeypatch.setattr(sequential.media, "extract_audio", lambda *_a, **_kw: [])
    monkeypatch.setattr(sequential.media, "probe_duration", lambda *_a, **_kw: 480.0)
    monkeypatch.setattr(sequential.transcribe, "transcript", lambda *_a, **_kw: "")

    captured: dict = {}

    def fake_complete(prompt, *, parts=None, model, **_kwargs):
        captured["prompt"] = prompt
        return json.dumps(
            {"statements": [], "ui_state": "", "open_questions": [], "resolved": []}
        )

    monkeypatch.setattr(sequential.llm, "complete", fake_complete)

    sequential.extract(tmp_path / "demo.mp4", _SEQUENTIAL_KNOBS)

    # 480s / 120s chunk_s = 4 windows, even though only 1 frame exists in total; only the
    # window holding that frame survives the empty-skip rule, but it must still report
    # the true chunk count.
    assert "1 of 4" in captured["prompt"]


# --- _video_corpus -------------------------------------------------------------


def test_video_corpus_renders_one_timestamped_quote_per_statement():
    # gap_audit reads this as the recording's source text: without it every video-derived
    # SOP fact would be reported as an unsupported hallucination.
    assert pipeline._video_corpus(VIDEO_STATEMENTS) == VIDEO_CORPUS


def test_video_corpus_skips_statements_without_a_quote():
    statements = [
        {"statement": "no quote", "supporting_media": "00:01"},
        {"supporting_quote": "  ", "supporting_media": "00:02"},
        {"supporting_quote": "Applicability: Applicable", "supporting_media": ""},
    ]
    assert pipeline._video_corpus(statements) == "- [] Applicability: Applicable"


# --- video extraction cache ----------------------------------------------------


def test_video_cache_hits_with_the_same_prompt(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"

    pipeline._write_video_cache(
        cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "audit corpus"
    )
    assert (cache_dir / "demo.mp4.json").is_file()
    assert pipeline._cached_video(cache_dir, doc, "prompt A") == (
        VIDEO_STATEMENTS,
        "audit corpus",
    )


def test_video_cache_misses_when_the_prompt_changes(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"
    pipeline._write_video_cache(cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "corpus")
    assert pipeline._cached_video(cache_dir, doc, "prompt B") is None


def test_video_cache_misses_when_a_decode_knob_changes(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"
    pipeline._write_video_cache(cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "corpus")

    # cache_key() folds in the strategy name and every sampling knob, so changing one of the
    # knobs must invalidate statements drawn from the previous plan.
    monkeypatch.setattr(pipeline.video, "cache_key", lambda: "naive:a-different-plan")
    assert pipeline._cached_video(cache_dir, doc, "prompt A") is None


def test_video_cache_misses_when_the_file_changes(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    path = write_mp4(tmp_path)
    doc = SourceDoc(name="demo.mp4", text="", path=path)
    cache_dir = tmp_path / "cache"
    pipeline._write_video_cache(cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "corpus")

    path.write_bytes(b"\x00a different recording")
    assert pipeline._cached_video(cache_dir, doc, "prompt A") is None


def test_video_cache_hit_restores_doc_text_without_decoding(monkeypatch, tmp_path):
    _, calls = install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"
    pipeline._write_video_cache(
        cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "[00:04] the audit corpus"
    )
    doc.text = ""

    statements, was_cached = pipeline._extract_video(doc, "prompt A", cache_dir, False)
    assert was_cached is True
    assert statements == VIDEO_STATEMENTS
    assert doc.text == "[00:04] the audit corpus"
    assert calls["extract"] == 0  # no ffmpeg, no ASR on a hit


def test_extract_video_writes_the_cache_and_the_audit_corpus(monkeypatch, tmp_path):
    _, calls = install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"

    statements, was_cached = pipeline._extract_video(doc, "prompt A", cache_dir, False)
    assert was_cached is False
    assert calls["extract"] == 1
    assert doc.text == VIDEO_CORPUS

    payload = json.loads((cache_dir / "demo.mp4.json").read_text(encoding="utf-8"))
    assert payload["statements"] == statements
    assert payload["source_text"] == doc.text
    assert payload["hash"] == pipeline._video_cache_key(doc, "prompt A")


def test_extract_video_force_bypasses_a_valid_cache(monkeypatch, tmp_path):
    _, calls = install_fake_video(monkeypatch)
    doc = SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path))
    cache_dir = tmp_path / "cache"
    pipeline._write_video_cache(cache_dir, doc, "prompt A", VIDEO_STATEMENTS, "corpus")

    _, was_cached = pipeline._extract_video(doc, "prompt A", cache_dir, True)
    assert was_cached is False
    assert calls["extract"] == 1


# --- extract() routing ---------------------------------------------------------


def test_extract_routes_a_recording_to_the_video_branch(monkeypatch, tmp_path):
    _, calls = install_fake_video(monkeypatch)

    def boom(*_args, **_kwargs):
        raise AssertionError("the text path must not run for a recording")

    monkeypatch.setattr(pipeline, "_extract_one", boom)

    mp4 = write_mp4(tmp_path)
    doc = SourceDoc(name="demo.mp4", text="", path=mp4)
    statements = pipeline.extract([doc], cache_dir=None)

    assert calls["extract"] == 1
    assert calls["path"] == mp4
    assert len(statements) == 1


def test_extract_routes_markdown_to_the_text_template(monkeypatch, tmp_path):
    fake, calls = install_fake_video(monkeypatch)

    def boom(*_args, **_kwargs):
        raise AssertionError("the video path must not run for a .md file")

    fake.extract = boom

    captured: dict = {}

    def fake_extract_one(doc, template):
        captured["template"] = template
        return [{"statement": "from text"}]

    monkeypatch.setattr(pipeline, "_extract_one", fake_extract_one)

    doc = SourceDoc(name="notes.md", text="body")
    statements = pipeline.extract([doc], cache_dir=None)

    assert calls["extract"] == 0
    assert captured["template"] == load_prompt("02_extract.md")
    assert statements == [{"statement": "from text", "source": "notes.md"}]


def test_extract_tags_source_and_keeps_supporting_media(monkeypatch, tmp_path):
    install_fake_video(monkeypatch)
    monkeypatch.setattr(
        pipeline, "_extract_one", lambda _doc, _t: [{"statement": "from text"}]
    )

    docs = [
        SourceDoc(name="notes.md", text="body"),
        SourceDoc(name="demo.mp4", text="", path=write_mp4(tmp_path)),
    ]
    statements = pipeline.extract(docs, cache_dir=None)

    by_source = {s["source"]: s for s in statements}
    assert by_source["notes.md"]["statement"] == "from text"
    assert by_source["demo.mp4"]["supporting_media"] == "04:12–04:31"
    assert "supporting_media" not in by_source["notes.md"]


# --- load_corpus ---------------------------------------------------------------


def test_load_corpus_records_a_recording_by_path_only(tmp_path):
    (tmp_path / "notes.md").write_text("body", encoding="utf-8")
    mp4 = write_mp4(tmp_path)

    docs = {doc.name: doc for doc in load_corpus(tmp_path)}
    assert set(docs) == {"notes.md", "demo.mp4"}

    recording = docs["demo.mp4"]
    assert recording.name == "demo.mp4"
    assert recording.text == ""
    assert recording.path == mp4
    assert recording.is_video() is True
    assert docs["notes.md"].path is None
    assert docs["notes.md"].is_video() is False


def test_load_corpus_accepts_a_video_only_folder(tmp_path):
    write_mp4(tmp_path)
    docs = load_corpus(tmp_path)
    assert [doc.name for doc in docs] == ["demo.mp4"]


def test_load_corpus_is_case_insensitive_about_the_suffix(tmp_path):
    write_mp4(tmp_path, name="DEMO.MP4")
    docs = load_corpus(tmp_path)
    assert [doc.name for doc in docs] == ["DEMO.MP4"]
    assert docs[0].is_video() is True


def test_load_corpus_still_skips_unsupported_and_empty_files(tmp_path):
    write_mp4(tmp_path)
    (tmp_path / "clip.mov").write_bytes(b"\x00mov")
    (tmp_path / "sheet.xlsx").write_bytes(b"\x00xlsx")
    (tmp_path / ".hidden.md").write_text("body", encoding="utf-8")
    (tmp_path / "blank.md").write_text("   \n", encoding="utf-8")

    assert [doc.name for doc in load_corpus(tmp_path)] == ["demo.mp4"]


def test_load_corpus_raises_when_nothing_is_readable(tmp_path):
    (tmp_path / "clip.mov").write_bytes(b"\x00mov")
    with pytest.raises(ValueError, match="No readable inputs"):
        load_corpus(tmp_path)
