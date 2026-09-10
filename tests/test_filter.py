"""Unit tests for the filtering step (--sop-name): no API, no assumptions about any real
SOP content — just that a sop_name scopes the statement set down via the model's returned
indices, and that omitting it is a true no-op.
"""

from __future__ import annotations

from sop_pipeline import pipeline
from sop_pipeline.pipeline import (
    _cached_filtered,
    _write_filter_cache,
    filter_by_sop,
)


_STATEMENTS = [
    {"target_section": "step", "statement": "PFML fact", "source": "a.md"},
    {"target_section": "step", "statement": "STD fact", "source": "a.md"},
    {"target_section": "step", "statement": "another PFML fact", "source": "b.md"},
]


def test_filter_is_a_noop_without_a_sop_name(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("llm.complete must not be called when sop_name is empty")

    monkeypatch.setattr(pipeline.llm, "complete", fail_if_called)

    assert filter_by_sop(_STATEMENTS, "") == _STATEMENTS


def test_filter_keeps_only_the_returned_indices_unmodified(monkeypatch):
    monkeypatch.setattr(
        pipeline.llm, "complete", lambda *_a, **_k: '{"keep_indices": [0, 2]}'
    )

    filtered = filter_by_sop(_STATEMENTS, "PFML process")

    assert filtered == [_STATEMENTS[0], _STATEMENTS[2]]
    assert filtered[0] is _STATEMENTS[0]  # selected, not rebuilt from model output
    assert filtered[1] is _STATEMENTS[2]


def test_filter_out_of_range_indices_are_dropped_not_raised(monkeypatch):
    monkeypatch.setattr(
        pipeline.llm, "complete", lambda *_a, **_k: '{"keep_indices": [0, 99, -1]}'
    )

    assert filter_by_sop(_STATEMENTS, "PFML process") == [_STATEMENTS[0]]


def test_filter_prompt_includes_sop_name_and_indexed_statements(monkeypatch):
    captured: dict[str, str] = {}

    def fake_complete(prompt, **_kwargs):
        captured["prompt"] = prompt
        return '{"keep_indices": []}'

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)

    filter_by_sop(_STATEMENTS, "PFML process")

    assert "PFML process" in captured["prompt"]
    assert '"index": 0' in captured["prompt"]
    assert '"statement": "PFML fact"' in captured["prompt"]
    # The lightweight indexed summary is sent, not the raw statement dicts (no "source"
    # key from the original dict order, but source IS carried through under that name).
    assert '"target_section": "step"' in captured["prompt"]


# --- cache -------------------------------------------------------------------


def test_filter_cache_hits_with_same_prompt_and_sop_name(tmp_path):
    _write_filter_cache(
        tmp_path, _STATEMENTS, "template A" + "PFML process", [_STATEMENTS[0]]
    )
    assert _cached_filtered(tmp_path, _STATEMENTS, "template A" + "PFML process") == [
        _STATEMENTS[0]
    ]


def test_filter_cache_misses_when_sop_name_changes(tmp_path):
    _write_filter_cache(
        tmp_path, _STATEMENTS, "template A" + "PFML process", [_STATEMENTS[0]]
    )
    # Same statements, same template text, different sop_name folded into prompt_text.
    assert _cached_filtered(tmp_path, _STATEMENTS, "template A" + "STD process") is None


def test_filter_uses_cache_instead_of_calling_the_model(monkeypatch, tmp_path):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("llm.complete must not be called on a cache hit")

    monkeypatch.setattr(pipeline.llm, "complete", fail_if_called)
    template = pipeline.load_prompt("02b_filter_by_sop.md")
    _write_filter_cache(
        tmp_path, _STATEMENTS, template + "PFML process", [_STATEMENTS[1]]
    )

    result = filter_by_sop(_STATEMENTS, "PFML process", cache_dir=tmp_path)

    assert result == [_STATEMENTS[1]]
