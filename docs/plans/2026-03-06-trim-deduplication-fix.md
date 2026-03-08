# Trim Deduplication Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent hooks from repeating after `trim_store` discards old collections by maintaining a persistent `seen_urls` list that survives trimming.

**Architecture:** Add a top-level `"seen_urls"` key to the store JSON that accumulates every hook URL ever fetched. `stored_urls()` returns the union of this list and the current collections (for backward compatibility with old caches). `ensure_fresh()` extends `seen_urls` whenever it appends a new collection, before `trim_store` runs. No trimming of `seen_urls` — the list grows slowly (a handful of URLs per day) and stays small in practice.

**Tech Stack:** Python 3, pytest, `scripts/dyk.py`, `tests/test_dyk.py`

---

### Task 1: Write a failing test — `stored_urls` reads from `seen_urls` key

**Files:**
- Modify: `tests/test_dyk.py` — add to `class TestStoredUrls`

**Step 1: Write the failing test**

Add this test inside `class TestStoredUrls` (after `test_collects_urls_from_store`, around line 269):

```python
def test_includes_urls_from_seen_urls_key(self):
    store = {
        "seen_urls": ["https://en.wikipedia.org/wiki/Trimmed_Article"],
        "collections": [],
    }
    assert "https://en.wikipedia.org/wiki/Trimmed_Article" in dyk.stored_urls(store)
```

**Step 2: Run the test to verify it fails**

```bash
python3 -m pytest tests/test_dyk.py::TestStoredUrls::test_includes_urls_from_seen_urls_key -v
```

Expected: `FAILED` — `stored_urls` currently ignores the `seen_urls` key.

---

### Task 2: Implement — make `stored_urls` read from `seen_urls`

**Files:**
- Modify: `scripts/dyk.py:198-204`

**Step 1: Replace `stored_urls` with this implementation**

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

**Step 2: Run all tests to verify green**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass, including the new test.

**Step 3: Commit**

```bash
git add tests/test_dyk.py scripts/dyk.py
git commit -m "fix: stored_urls reads from persistent seen_urls history"
```

---

### Task 3: Write a failing test — `ensure_fresh` populates `seen_urls`

**Files:**
- Modify: `tests/test_dyk.py` — add to `class TestEnsureToday`

**Step 1: Write the failing test**

Add this test inside `class TestEnsureToday` (after `test_sets_last_checked_at_on_fetch_failure`, around line 515):

```python
def test_persists_hook_urls_to_seen_urls(self, monkeypatch):
    """ensure_fresh must add new hook URLs to seen_urls so trim_store
    cannot cause them to be re-fetched on a later refresh."""
    now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(dyk, "now_utc", lambda: now)
    store = {
        "collections": [
            {"date": "2026-02-23", "fetched_at": "2026-02-23T00:00:00Z", "hooks": []}
        ]
    }
    monkeypatch.setattr(
        dyk,
        "collect_hooks",
        lambda **_kwargs: [
            {"text": "fact", "urls": ["https://en.wikipedia.org/wiki/Article_A"], "returned": False}
        ],
    )

    dyk.ensure_fresh(store)

    assert "https://en.wikipedia.org/wiki/Article_A" in store.get("seen_urls", [])
```

**Step 2: Run the test to verify it fails**

```bash
python3 -m pytest tests/test_dyk.py::TestEnsureToday::test_persists_hook_urls_to_seen_urls -v
```

Expected: `FAILED` — `ensure_fresh` does not yet write to `seen_urls`.

---

### Task 4: Write a failing regression test — trim does not lose seen URLs

**Files:**
- Modify: `tests/test_dyk.py` — add to `class TestEnsureToday`

**Step 1: Write the failing test**

Add this test inside `class TestEnsureToday`:

```python
def test_seen_urls_survives_trim_store(self, monkeypatch):
    """URLs from a trimmed collection must still appear in stored_urls,
    preventing Wikipedia from re-serving a hook the user has already seen."""
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(dyk, "now_utc", lambda: now)

    # Fill store to MAX_COLLECTIONS with one hook each; all hooks served.
    store = {
        "collections": [
            {
                "date": f"2026-02-{i:02d}",
                "fetched_at": f"2026-02-{i:02d}T12:00:00Z",
                "hooks": [
                    {
                        "text": f"fact {i}",
                        "urls": [f"https://en.wikipedia.org/wiki/Article_{i}"],
                        "returned": True,
                    }
                ],
            }
            for i in range(1, dyk.MAX_COLLECTIONS + 1)
        ],
        # seen_urls already accumulated from previous runs
        "seen_urls": [
            f"https://en.wikipedia.org/wiki/Article_{i}"
            for i in range(1, dyk.MAX_COLLECTIONS + 1)
        ],
    }

    # 11th fetch brings one genuinely new hook; this will trigger a trim.
    monkeypatch.setattr(
        dyk,
        "collect_hooks",
        lambda **_kwargs: [
            {
                "text": "new fact",
                "urls": ["https://en.wikipedia.org/wiki/Article_New"],
                "returned": False,
            }
        ],
    )

    dyk.ensure_fresh(store)

    # trim_store removed collection 1 (Article_1), but seen_urls must
    # still include it so it can never be re-fetched.
    assert len(store["collections"]) == dyk.MAX_COLLECTIONS
    urls = dyk.stored_urls(store)
    assert "https://en.wikipedia.org/wiki/Article_1" in urls
```

**Step 2: Run the test to verify it fails**

```bash
python3 -m pytest tests/test_dyk.py::TestEnsureToday::test_seen_urls_survives_trim_store -v
```

Expected: `FAILED` — currently trimming loses Article_1.

Note: once Task 5 is complete this test will pass. Writing it now locks in the requirement before touching the implementation.

---

### Task 5: Implement — `ensure_fresh` extends `seen_urls` before trimming

**Files:**
- Modify: `scripts/dyk.py:280-287` (the `collections.append(...)` block inside `ensure_fresh`)

**Step 1: Update the append block in `ensure_fresh`**

Replace:
```python
    collections.append(
        {
            "date": now.date().isoformat(),
            "fetched_at": to_iso_z(now),
            "hooks": hooks,
        }
    )
    trim_store(store)
```

With:
```python
    collections.append(
        {
            "date": now.date().isoformat(),
            "fetched_at": to_iso_z(now),
            "hooks": hooks,
        }
    )
    # Accumulate hook URLs in a persistent history so trim_store cannot
    # cause already-seen hooks to be re-fetched from Wikipedia.
    seen = store.setdefault("seen_urls", [])
    seen.extend(url for hook in hooks for url in hook.get("urls", []))
    trim_store(store)
```

**Step 2: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass, including the two new `TestEnsureToday` tests.

**Step 3: Commit**

```bash
git add tests/test_dyk.py scripts/dyk.py
git commit -m "fix: accumulate seen_urls in store so trim_store cannot re-expose hooks"
```

---

## Done

All tests green. The fix is two small, independent changes:

1. `stored_urls` unions `seen_urls` with current-collection URLs.
2. `ensure_fresh` extends `seen_urls` before calling `trim_store`.

Old caches without `seen_urls` continue to work — they fall back to collection scanning until a fresh fetch populates the key.
