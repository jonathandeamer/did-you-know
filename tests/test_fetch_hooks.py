#!/usr/bin/env python3
"""Unit tests for scripts/fetch_hooks.py.

Run with: python3 -m pytest tests/ -v
Requires: pip install pytest
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import fetch_hooks
import helpers
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
    # Pin now to 1 day after existing collection so trim_store keeps it.
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc))
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


def test_fetch_and_stage_sets_last_checked_at_on_success(monkeypatch):
    now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [dict(_SAMPLE_HOOK)])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"


def test_fetch_and_stage_sets_last_checked_at_on_all_duplicates(monkeypatch):
    now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
    assert store["collections"] == []


def test_fetch_and_stage_sets_last_checked_at_on_fetch_failure(monkeypatch):
    now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    existing = {"date": "2026-01-01", "fetched_at": "2026-01-01T00:00:00Z", "hooks": []}
    store = {"collections": [existing], "seen_urls": []}
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)

    def _fail(**kw):
        raise RuntimeError("network error")

    monkeypatch.setattr("fetch_hooks.collect_hooks", _fail)
    fetch_and_stage(store)
    assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"


def test_fetch_and_stage_persists_hook_urls_to_seen_urls(monkeypatch):
    store = _due_store()
    monkeypatch.setattr("fetch_hooks.collect_hooks", lambda **kw: [dict(_SAMPLE_HOOK)])
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)
    assert "https://en.wikipedia.org/wiki/Foo" in store.get("seen_urls", [])


def test_fetch_and_stage_seen_urls_survives_trim_store(monkeypatch):
    """URLs from an expired collection must still appear in stored_urls."""
    now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)

    store = {
        "collections": [
            {
                "date": "2026-03-01",
                "fetched_at": "2026-03-01T12:00:00Z",  # 9 days ago — > MAX_HOOK_AGE_DAYS (8), expired
                "hooks": [
                    {
                        "text": "old fact",
                        "urls": ["https://en.wikipedia.org/wiki/Article_Old"],
                        "returned": True,
                        "tags": None,
                    }
                ],
            },
            {
                "date": "2026-03-09",
                "fetched_at": "2026-03-09T12:00:00Z",  # 1 day ago — < MAX_HOOK_AGE_DAYS (8), kept
                "hooks": [
                    {
                        "text": "recent fact",
                        "urls": ["https://en.wikipedia.org/wiki/Article_Recent"],
                        "returned": True,
                        "tags": None,
                    }
                ],
            },
        ],
    }
    monkeypatch.setattr(
        "fetch_hooks.collect_hooks",
        lambda **kw: [
            {
                "text": "new fact",
                "urls": ["https://en.wikipedia.org/wiki/Article_New"],
                "returned": False,
            }
        ],
    )
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)
    fetch_and_stage(store)

    # Expired collection was trimmed; recent collection was kept.
    assert all(c["fetched_at"] != "2026-03-01T12:00:00Z" for c in store["collections"])
    assert any(c["fetched_at"] == "2026-03-09T12:00:00Z" for c in store["collections"])
    # Expired collection's URL must still be in seen_urls.
    urls = helpers.stored_urls(store)
    assert "https://en.wikipedia.org/wiki/Article_Old" in urls


def test_main_saves_store_after_fetch_failure_with_no_cache(tmp_path, monkeypatch):
    now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("helpers.DATA_PATH", tmp_path / "store.json")
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)
    monkeypatch.setattr("fetch_hooks.refresh_due", lambda s, n: True)

    def _fail(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("fetch_hooks.collect_hooks", _fail)
    result = fetch_hooks.main()
    assert result == 1
    assert (tmp_path / "store.json").exists(), "store was never saved to disk"
    saved = json.loads((tmp_path / "store.json").read_text())
    assert saved.get("last_checked_at") == "2026-02-24T12:00:00Z"
