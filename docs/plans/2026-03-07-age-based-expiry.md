# Age-Based Hook Expiry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the count-based `MAX_COLLECTIONS = 10` retention limit with age-based expiry that drops any collection fetched 8 or more days ago.

**Architecture:** `trim_store` in `helpers.py` gains a `now: datetime` parameter and filters by `fetched_at` age instead of counting. Both callers (`ensure_fresh` in `serve_hook.py` and `fetch_and_stage` in `fetch_hooks.py`) already have `now` in scope and simply pass it through. The `seen_urls` deduplication is unaffected.

**Tech Stack:** Python 3.8+, pytest

---

### Context for the implementer

The cache at `~/.openclaw/dyk-facts.json` holds a list of `collections`, each stamped with a `fetched_at` ISO 8601 timestamp. Currently `trim_store` removes the oldest entries once the list exceeds 10. The new behaviour: remove any collection whose `fetched_at` is 8 or more days before `now`. Collections with a missing or unparseable `fetched_at` are treated as expired and dropped.

The constant `MAX_COLLECTIONS` is referenced in two integration tests (`test_serve_hook.py` and `test_fetch_hooks.py`) that simulate filling the store to capacity before triggering a trim. Those tests need to be rewritten to use age-based fixtures instead.

`docs/` is gitignored — do not try to commit this plan file.

---

### Task 1: Replace `trim_store` with age-based logic

**Files:**
- Modify: `scripts/helpers.py` (lines 7, 36, 256–260)
- Modify: `tests/test_helpers.py` — remove `test_trim_store_keeps_max_days` from `TestStoreHelpers`, add new `TestTrimStore` class

---

**Step 1: Write the failing tests**

In `tests/test_helpers.py`, delete the existing `test_trim_store_keeps_max_days` method from `TestStoreHelpers` and add a new `TestTrimStore` class after `TestStoreHelpers`:

```python
class TestTrimStore:
    def test_drops_collections_older_than_max_age(self):
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"fetched_at": "2026-03-01T12:00:00Z", "hooks": []},  # 9 days ago — drop
                {"fetched_at": "2026-03-02T12:00:00Z", "hooks": []},  # 8 days ago — drop (boundary)
                {"fetched_at": "2026-03-03T12:00:00Z", "hooks": []},  # 7 days ago — keep
                {"fetched_at": "2026-03-10T10:00:00Z", "hooks": []},  # today — keep
            ]
        }
        helpers.trim_store(store, now)
        assert len(store["collections"]) == 2
        assert store["collections"][0]["fetched_at"] == "2026-03-03T12:00:00Z"
        assert store["collections"][1]["fetched_at"] == "2026-03-10T10:00:00Z"

    def test_drops_collection_at_exact_boundary(self):
        # A collection fetched exactly 8 days ago must be dropped.
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"fetched_at": "2026-03-02T12:00:00Z", "hooks": []},  # exactly 8 days ago
            ]
        }
        helpers.trim_store(store, now)
        assert store["collections"] == []

    def test_keeps_collection_just_inside_boundary(self):
        # A collection fetched 1 second under 8 days ago must be kept.
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"fetched_at": "2026-03-02T12:00:01Z", "hooks": []},  # 7d 23h 59m 59s ago
            ]
        }
        helpers.trim_store(store, now)
        assert len(store["collections"]) == 1

    def test_drops_collection_with_missing_fetched_at(self):
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"hooks": []},  # no fetched_at — treat as expired
                {"fetched_at": "2026-03-09T12:00:00Z", "hooks": []},  # 1 day ago — keep
            ]
        }
        helpers.trim_store(store, now)
        assert len(store["collections"]) == 1
        assert store["collections"][0]["fetched_at"] == "2026-03-09T12:00:00Z"

    def test_keeps_all_when_all_recent(self):
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"fetched_at": "2026-03-08T12:00:00Z", "hooks": []},
                {"fetched_at": "2026-03-09T12:00:00Z", "hooks": []},
                {"fetched_at": "2026-03-10T10:00:00Z", "hooks": []},
            ]
        }
        helpers.trim_store(store, now)
        assert len(store["collections"]) == 3

    def test_empties_store_when_all_expired(self):
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        store = {
            "collections": [
                {"fetched_at": "2026-02-01T12:00:00Z", "hooks": []},
                {"fetched_at": "2026-02-15T12:00:00Z", "hooks": []},
            ]
        }
        helpers.trim_store(store, now)
        assert store["collections"] == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_helpers.py::TestTrimStore -v
```

Expected: all 6 tests FAIL — `trim_store()` takes 1 positional argument but 2 were given (or wrong behavior).

**Step 3: Update `helpers.py`**

a) Add `timedelta` to the datetime import (line 7):

```python
from datetime import datetime, timedelta, timezone
```

b) Replace `MAX_COLLECTIONS = 10` (line 36) with:

```python
MAX_HOOK_AGE_DAYS = 8  # drop collections fetched this many days ago or more
```

c) Replace the entire `trim_store` function (lines 256–260) with:

```python
def trim_store(store: dict, now: datetime) -> None:
    """Drop collections fetched MAX_HOOK_AGE_DAYS or more days ago."""
    cutoff = now - timedelta(days=MAX_HOOK_AGE_DAYS)
    collections = store.setdefault("collections", [])
    store["collections"] = [
        col for col in collections
        if (ts := parse_iso(col.get("fetched_at", ""))) is not None and ts > cutoff
    ]
```

**Step 4: Run the new tests to verify they pass**

```bash
pytest tests/test_helpers.py::TestTrimStore -v
```

Expected: all 6 PASS.

**Step 5: Run the full suite to see what else broke**

```bash
pytest -v
```

Expected: `TestStoreHelpers::test_trim_store_keeps_max_days` is gone (deleted in Step 1). The two integration tests (`test_seen_urls_survives_trim_store` in `test_serve_hook.py` and `test_fetch_hooks.py`) will FAIL because they reference `helpers.MAX_COLLECTIONS` and call `trim_store` with the old signature. That is expected — they will be fixed in Task 2.

Also expect failures in `serve_hook.py` and `fetch_hooks.py` themselves when `trim_store` is called at runtime (wrong number of arguments) — but those are not directly exercised by the remaining passing tests.

**Step 6: Commit**

```bash
git add scripts/helpers.py tests/test_helpers.py
git commit -m "refactor: replace MAX_COLLECTIONS with age-based trim_store (8-day expiry)"
```

---

### Task 2: Update callers and integration tests

**Files:**
- Modify: `scripts/serve_hook.py` (line 76)
- Modify: `scripts/fetch_hooks.py` (line 63)
- Modify: `tests/test_serve_hook.py` (lines 170–215)
- Modify: `tests/test_fetch_hooks.py` (lines 164–198)

---

**Step 1: Update `serve_hook.py`**

Line 76 — change `trim_store(store)` to `trim_store(store, now)`:

```python
    trim_store(store, now)
```

(`now` is already defined at the top of `ensure_fresh`.)

**Step 2: Update `fetch_hooks.py`**

Line 63 — change `trim_store(store)` to `trim_store(store, now)`:

```python
    trim_store(store, now)
```

(`now` is already defined at the top of `fetch_and_stage`.)

**Step 3: Run the full suite — only the two integration tests should still fail**

```bash
pytest -v
```

Expected: everything passes except `test_seen_urls_survives_trim_store` in `test_serve_hook.py` and `test_fetch_and_stage_seen_urls_survives_trim_store` in `test_fetch_hooks.py` (both still reference `helpers.MAX_COLLECTIONS`).

**Step 4: Rewrite `test_serve_hook.py::TestEnsureFresh::test_seen_urls_survives_trim_store`**

Replace the entire method body (lines 170–215). The goal is identical — verify that URLs from a trimmed collection are preserved in `seen_urls` — but the fixture now uses age-based timestamps instead of filling to `MAX_COLLECTIONS`.

```python
    def test_seen_urls_survives_trim_store(self, monkeypatch):
        """URLs from an expired collection must still appear in stored_urls,
        preventing Wikipedia from re-serving a hook the user has already seen."""
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)

        # One expired collection (9 days ago — will be trimmed) and one recent.
        # No seen_urls key — simulates a legacy cache; ensure_fresh must backfill.
        store = {
            "collections": [
                {
                    "date": "2026-03-01",
                    "fetched_at": "2026-03-01T12:00:00Z",  # 9 days ago — expired
                    "hooks": [
                        {
                            "text": "old fact",
                            "urls": ["https://en.wikipedia.org/wiki/Article_Old"],
                            "returned": True,
                        }
                    ],
                },
                {
                    "date": "2026-03-09",
                    "fetched_at": "2026-03-09T12:00:00Z",  # 1 day ago — kept
                    "hooks": [
                        {
                            "text": "recent fact",
                            "urls": ["https://en.wikipedia.org/wiki/Article_Recent"],
                            "returned": True,
                        }
                    ],
                },
            ],
        }

        # New fetch brings a genuinely new hook, triggering a trim.
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [
                {
                    "text": "new fact",
                    "urls": ["https://en.wikipedia.org/wiki/Article_New"],
                    "returned": False,
                }
            ],
        )

        serve_hook.ensure_fresh(store)

        # Expired collection was trimmed.
        assert all(c["fetched_at"] != "2026-03-01T12:00:00Z" for c in store["collections"])
        # But its URL must still be in seen_urls.
        urls = helpers.stored_urls(store)
        assert "https://en.wikipedia.org/wiki/Article_Old" in urls
```

**Step 5: Rewrite `test_fetch_hooks.py::test_fetch_and_stage_seen_urls_survives_trim_store`**

Same goal, same approach. Replace the entire function:

```python
def test_fetch_and_stage_seen_urls_survives_trim_store(monkeypatch):
    """URLs from an expired collection must still appear in stored_urls."""
    now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("fetch_hooks.now_utc", lambda: now)

    store = {
        "collections": [
            {
                "date": "2026-03-01",
                "fetched_at": "2026-03-01T12:00:00Z",  # 9 days ago — expired
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
                "fetched_at": "2026-03-09T12:00:00Z",  # 1 day ago — kept
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

    # Expired collection was trimmed.
    assert all(c["fetched_at"] != "2026-03-01T12:00:00Z" for c in store["collections"])
    # But its URL must still be in seen_urls.
    urls = helpers.stored_urls(store)
    assert "https://en.wikipedia.org/wiki/Article_Old" in urls
```

**Step 6: Run the full suite — all tests must pass**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 7: Commit**

```bash
git add scripts/serve_hook.py scripts/fetch_hooks.py tests/test_serve_hook.py tests/test_fetch_hooks.py
git commit -m "refactor: update trim_store callers and integration tests for age-based expiry"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

CLAUDE.md is gitignored — no commit needed.

**Step 1: Update the Constants & Configuration section**

Find the line:
```
- `helpers.py`: `API_URL`, `DATA_PATH`, `MAX_COLLECTIONS`, `REFRESH_INTERVAL`, ...
```

Replace `MAX_COLLECTIONS` with `MAX_HOOK_AGE_DAYS`:
```
- `helpers.py`: `API_URL`, `DATA_PATH`, `MAX_HOOK_AGE_DAYS`, `REFRESH_INTERVAL`, ...
```

**Step 2: Update the Architecture section if it mentions MAX_COLLECTIONS**

Search for any remaining `MAX_COLLECTIONS` references and replace with `MAX_HOOK_AGE_DAYS`.

**Step 3: Verify no remaining MAX_COLLECTIONS references in tracked files**

```bash
grep -r "MAX_COLLECTIONS" scripts/ tests/
```

Expected: no output.
