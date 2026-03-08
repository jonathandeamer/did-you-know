# State Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent crashes when the cache JSON has null values in expected list fields, and pin the version-upgrade migration contract with an explicit end-to-end test.

**Architecture:** Two production fixes in `scripts/dyk.py` — strengthen `load_store` to reject a `"collections"` value that isn't a list (and strip a `"seen_urls"` value that isn't a list), and change `stored_urls` to use `or []` guards so null `"hooks"` or `"urls"` values in stored hooks don't crash iteration. One additional contract test pins the backward-compat migration story (old cache → first refresh → `seen_urls` populated). All changes follow red/green TDD: failing tests first, minimal implementation second.

**Tech Stack:** Python 3, pytest, `scripts/dyk.py`, `tests/test_dyk.py`

---

### Task 1: Write failing tests — `load_store` null field handling

**Files:**
- Modify: `tests/test_dyk.py` — add two tests to `class TestStoreHelpers`

**Step 1: Write the failing tests**

Add both tests inside `class TestStoreHelpers`, after `test_load_store_dict_without_collections_returns_default` (around line 301):

```python
def test_load_store_null_collections_returns_default(self, monkeypatch, tmp_path):
    # {"collections": null} passes the "key exists" check but must be
    # treated as invalid — null is not a usable collection list.
    data_path = tmp_path / "dyk.json"
    data_path.write_text('{"collections": null}', encoding="utf-8")
    monkeypatch.setattr(dyk, "DATA_PATH", data_path)
    assert dyk.load_store() == {"collections": []}

def test_load_store_null_seen_urls_is_stripped(self, monkeypatch, tmp_path):
    # {"collections": [], "seen_urls": null} — collections are valid but
    # seen_urls is corrupted; strip it to [] rather than discarding the cache.
    data_path = tmp_path / "dyk.json"
    data_path.write_text('{"collections": [], "seen_urls": null}', encoding="utf-8")
    monkeypatch.setattr(dyk, "DATA_PATH", data_path)
    result = dyk.load_store()
    assert result["collections"] == []
    assert result.get("seen_urls") == []
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_dyk.py::TestStoreHelpers::test_load_store_null_collections_returns_default tests/test_dyk.py::TestStoreHelpers::test_load_store_null_seen_urls_is_stripped -v
```

Expected: both `FAILED`. The first returns `{"collections": None}` instead of `{"collections": []}`. The second returns `{"collections": [], "seen_urls": None}` instead of stripping `seen_urls`.

---

### Task 2: Implement — strengthen `load_store` validation

**Files:**
- Modify: `scripts/dyk.py` — update `load_store` (around line 228)

**Step 1: Replace the validation block in `load_store`**

Current code (two lines inside the try block):
```python
        if not isinstance(data, dict) or "collections" not in data:
            return {"collections": []}
        return data
```

Replace with:
```python
        if not isinstance(data, dict) or not isinstance(data.get("collections"), list):
            return {"collections": []}
        if not isinstance(data.get("seen_urls", []), list):
            data["seen_urls"] = []
        return data
```

The first line now uses `isinstance(..., list)` instead of a key-presence check, so `"collections": null` and `"collections": {}` both return the safe default. The second line strips a corrupted `"seen_urls"` value to `[]` rather than discarding the entire cache.

**Step 2: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass (74 tests — 72 existing + 2 new).

**Step 3: Commit**

```bash
git add tests/test_dyk.py scripts/dyk.py
git commit -m "fix: load_store rejects null collections and strips null seen_urls"
```

---

### Task 3: Write failing tests — `stored_urls` null hooks/urls handling

**Files:**
- Modify: `tests/test_dyk.py` — add two tests to `class TestStoredUrls`

**Step 1: Write the failing tests**

Add both tests inside `class TestStoredUrls`, after `test_includes_urls_from_seen_urls_key` (around line 276):

```python
def test_null_hooks_in_collection_returns_empty(self):
    # A collection whose "hooks" key is null must not crash stored_urls.
    # This can arise from manual edits or future schema changes.
    store = {
        "collections": [{"date": "2026-02-24", "hooks": None}],
    }
    assert dyk.stored_urls(store) == set()

def test_null_urls_in_hook_skips_hook(self):
    # A hook whose "urls" key is null must not crash stored_urls.
    store = {
        "collections": [
            {
                "date": "2026-02-24",
                "hooks": [
                    {"text": "fine hook", "urls": ["https://en.wikipedia.org/wiki/Fine"], "returned": False},
                    {"text": "bad hook",  "urls": None, "returned": False},
                ],
            }
        ]
    }
    urls = dyk.stored_urls(store)
    assert "https://en.wikipedia.org/wiki/Fine" in urls
    # bad hook contributed nothing — no crash
    assert len(urls) == 1
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_dyk.py::TestStoredUrls::test_null_hooks_in_collection_returns_empty tests/test_dyk.py::TestStoredUrls::test_null_urls_in_hook_skips_hook -v
```

Expected: both `FAILED` with `TypeError: 'NoneType' object is not iterable`.

---

### Task 4: Implement — null-safe iteration in `stored_urls`

**Files:**
- Modify: `scripts/dyk.py` — update `stored_urls` (around line 198)

**Step 1: Replace `stored_urls` with null-safe iteration**

Current:
```python
def stored_urls(store: dict) -> set[str]:
    """Collect all URLs seen across stored and trimmed collections."""
    urls: set[str] = set(
        urllib.parse.unquote(url) for url in store.get("seen_urls", [])
    )
    for coll in store.get("collections", []):
        for hook in coll.get("hooks", []):
            urls.update(urllib.parse.unquote(url) for url in hook.get("urls", []))
    return urls
```

Replace with:
```python
def stored_urls(store: dict) -> set[str]:
    """Collect all URLs seen across stored and trimmed collections."""
    urls: set[str] = set(
        urllib.parse.unquote(url) for url in (store.get("seen_urls") or [])
    )
    for coll in (store.get("collections") or []):
        for hook in (coll.get("hooks") or []):
            urls.update(urllib.parse.unquote(url) for url in (hook.get("urls") or []))
    return urls
```

The only change is replacing `.get(key, [])` with `.get(key) or []` on the three iterated fields. Both forms return `[]` when the key is absent, but `or []` also handles the case where the key is present with a `null` (None) value.

**Step 2: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass (76 tests).

**Step 3: Commit**

```bash
git add tests/test_dyk.py scripts/dyk.py
git commit -m "fix: stored_urls guards against null hooks/urls fields"
```

---

### Task 5: Add backward-compat contract test — version-upgrade migration

**Files:**
- Modify: `tests/test_dyk.py` — add one test to `class TestBackwardsCompatibility`

This test does NOT need a production code change — it pins the existing behaviour as a non-regression contract. Write it, verify it is **green immediately**, and commit.

**Step 1: Write the contract test**

Add inside `class TestBackwardsCompatibility`, after `test_old_cache_without_last_checked_at_still_serves` (near the end of the file):

```python
def test_old_cache_without_seen_urls_backfills_on_first_refresh(
    self, monkeypatch, tmp_path, capsys
):
    """After upgrading from a version that never wrote seen_urls, the first
    refresh must backfill seen_urls from existing collections so that
    trim_store can never later re-expose those URLs.

    Contract: old cache → refresh → seen_urls contains all pre-existing URLs.
    """
    data_path = tmp_path / "dyk.json"
    # Old-format cache: no seen_urls, no last_checked_at, stale fetched_at
    old_cache = {
        "collections": [
            {
                "date": "2026-02-23",
                "fetched_at": "2026-02-23T00:00:00Z",
                "hooks": [
                    {
                        "text": "old fact",
                        "urls": ["https://en.wikipedia.org/wiki/Old_Article"],
                        "returned": False,
                    }
                ],
            }
        ]
        # No seen_urls, no last_checked_at — as written by older versions
    }
    data_path.write_text(json.dumps(old_cache), encoding="utf-8")
    monkeypatch.setattr(dyk, "DATA_PATH", data_path)
    monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(
        dyk,
        "collect_hooks",
        lambda **_kwargs: [
            {
                "text": "new fact",
                "urls": ["https://en.wikipedia.org/wiki/New_Article"],
                "returned": False,
            }
        ],
    )

    result = dyk.main()

    assert result == 0
    saved = json.loads(data_path.read_text(encoding="utf-8"))
    # Pre-existing URL must be in seen_urls after the backfill
    assert "https://en.wikipedia.org/wiki/Old_Article" in saved.get("seen_urls", [])
    # Newly fetched URL must also be in seen_urls
    assert "https://en.wikipedia.org/wiki/New_Article" in saved.get("seen_urls", [])
```

**Step 2: Run test to verify it is green**

```bash
python3 -m pytest tests/test_dyk.py::TestBackwardsCompatibility::test_old_cache_without_seen_urls_backfills_on_first_refresh -v
```

Expected: `PASSED` immediately — this is a contract test pinning existing behaviour, not a new feature.

**Step 3: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass (77 tests).

**Step 4: Commit**

```bash
git add tests/test_dyk.py
git commit -m "test: pin seen_urls backfill contract for old-cache version upgrades"
```

---

## Done

Three commits:
1. `fix: load_store rejects null collections and strips null seen_urls` — prevents crash-loop on corrupted cache
2. `fix: stored_urls guards against null hooks/urls fields` — prevents crash on partially corrupted hook data
3. `test: pin seen_urls backfill contract for old-cache version upgrades` — non-regression contract for the migration story

Total: 77 tests, all green.
