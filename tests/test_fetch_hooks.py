# tests/test_fetch_hooks.py
"""Tests for scripts/fetch_hooks.py — fetch_and_stage() function."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import fetch_hooks
from fetch_hooks import fetch_and_stage


_SAMPLE_HOOK = {
    "text": "some fact",
    "urls": ["https://en.wikipedia.org/wiki/Foo"],
    "returned": False,
}


def _due_store():
    """Empty store that refresh_due() will consider overdue."""
    return {"collections": [], "seen_urls": []}


# ---------------------------------------------------------------------------
# fetch_and_stage
# ---------------------------------------------------------------------------

def test_fetch_and_stage_adds_tags_null(monkeypatch):
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [dict(_SAMPLE_HOOK)])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    hooks = store["collections"][0]["hooks"]
    assert all(h["tags"] is None for h in hooks)


def test_fetch_and_stage_noop_when_refresh_not_due(monkeypatch):
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: False)
    fetch_and_stage(store)
    assert store["collections"] == []


def test_fetch_and_stage_noop_on_all_duplicates(monkeypatch):
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    assert store["collections"] == []


def test_fetch_and_stage_network_failure_with_cache_is_graceful(monkeypatch):
    """When fetch fails but a cached collection exists, return gracefully."""
    existing = {"date": "2026-01-01", "fetched_at": "2026-01-01T00:00:00Z", "hooks": []}
    store = {"collections": [existing], "seen_urls": []}

    def _fail(**kw):
        raise RuntimeError("network error")

    monkeypatch.setattr("fetch_hooks.collect_hooks", _fail)
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)  # must not raise
    assert len(store["collections"]) == 1  # unchanged


def test_fetch_and_stage_network_failure_without_cache_raises(monkeypatch):
    """When fetch fails with no cache at all, the exception propagates."""
    store = _due_store()

    def _fail(**kw):
        raise RuntimeError("network error")

    monkeypatch.setattr("fetch_hooks.collect_hooks", _fail)
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    with pytest.raises(RuntimeError):
        fetch_and_stage(store)


def test_fetch_and_stage_does_not_modify_existing_collections(monkeypatch):
    existing_hook = {"text": "old fact", "urls": ["https://en.wikipedia.org/wiki/Old"], "returned": True}
    existing = {"date": "2026-01-01", "fetched_at": "2026-01-01T00:00:00Z", "hooks": [existing_hook]}
    store = {"collections": [existing], "seen_urls": []}
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [dict(_SAMPLE_HOOK)])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    assert store["collections"][0]["hooks"][0] == existing_hook


def test_main_exits_zero_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr("helpers.DATA_PATH", tmp_path / "store.json")
    monkeypatch.setattr("fetch_hooks.collect_hooks",
                        lambda **kw: [dict(_SAMPLE_HOOK)])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    assert fetch_hooks.main() == 0
    saved = json.loads((tmp_path / "store.json").read_text())
    assert len(saved["collections"]) == 1
    assert saved["collections"][0]["hooks"][0]["tags"] is None


def test_main_exits_one_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("helpers.DATA_PATH", tmp_path / "store.json")
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)

    def _fail(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("fetch_hooks.collect_hooks", _fail)
    assert fetch_hooks.main() == 1
