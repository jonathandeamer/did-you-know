# Preference-Based Hook Serving Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Score and serve hooks by user-declared domain/tone preferences loaded from `~/.openclaw/dyk-prefs.json`.

**Architecture:** Two new functions (`load_prefs`, `score_hook`) added to `helpers.py`; `next_hook` in `serve_hook.py` gains a `prefs` parameter and picks the highest-scored unreturned hook rather than the first one. Missing prefs file → all scores 0 → current behaviour preserved.

**Tech Stack:** Python 3.8+, pytest

---

### Context for the implementer

The cache at `~/.openclaw/dyk-facts.json` holds a list of `collections`. Each collection contains `hooks`, where each hook may have a `tags` field:

```json
{
  "text": "some fact",
  "urls": ["https://en.wikipedia.org/wiki/..."],
  "returned": false,
  "tags": {
    "domain": ["science"],
    "tone": "surprising",
    "low_confidence": false
  }
}
```

`tags` is `null` when a hook has never been run through `write_tags.py`. `low_confidence: true` means the tagger was uncertain about the assignment.

The prefs file (`~/.openclaw/dyk-prefs.json`) looks like:

```json
{
  "domain": { "science": 1, "military_history": -1 },
  "tone":   { "surprising": 1, "dark": -1 }
}
```

Valid scores: `1` (prefer), `0` (neutral), `-1` (avoid). Missing or `null` → 0.

Scoring rules:
- `hook_score = domain_score + tone_score`
- Untagged (`tags: null`) or low-confidence (`low_confidence: true`) → score 0, still eligible
- Domain score = sum of prefs scores for all domain tags (1–2 tags)
- Tone score = prefs score for the single tone tag

Serving order:
1. Score descending
2. Most recently fetched collection first (tiebreak)
3. Random among hooks with equal score from the same collection (tiebreak)
4. Hooks with negative scores are always served — never withheld

`docs/` is gitignored — do not try to commit this plan file.

---

### Task 1: `load_prefs` and `PREFS_PATH`

**Files:**
- Modify: `scripts/helpers.py`
- Modify: `tests/test_helpers.py`

---

**Step 1: Write the failing tests**

In `tests/test_helpers.py`, add a new `TestLoadPrefs` class after the existing `TestStoreHelpers` class (before `TestTrimStore`):

```python
class TestLoadPrefs:
    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(helpers, "PREFS_PATH", tmp_path / "dyk-prefs.json")
        assert helpers.load_prefs() == {}

    def test_invalid_json_returns_empty_and_warns(self, monkeypatch, tmp_path, capsys):
        prefs_path = tmp_path / "dyk-prefs.json"
        prefs_path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(helpers, "PREFS_PATH", prefs_path)
        result = helpers.load_prefs()
        assert result == {}
        assert capsys.readouterr().err  # warning printed to stderr

    def test_valid_prefs_returned(self, monkeypatch, tmp_path):
        prefs_path = tmp_path / "dyk-prefs.json"
        prefs = {"domain": {"science": 1}, "tone": {"dark": -1}}
        prefs_path.write_text(json.dumps(prefs), encoding="utf-8")
        monkeypatch.setattr(helpers, "PREFS_PATH", prefs_path)
        assert helpers.load_prefs() == prefs

    def test_non_dict_json_returns_empty(self, monkeypatch, tmp_path):
        prefs_path = tmp_path / "dyk-prefs.json"
        prefs_path.write_text("[1, 2, 3]", encoding="utf-8")
        monkeypatch.setattr(helpers, "PREFS_PATH", prefs_path)
        assert helpers.load_prefs() == {}
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_helpers.py::TestLoadPrefs -v
```

Expected: all 4 FAIL — `AttributeError: module 'helpers' has no attribute 'PREFS_PATH'`

**Step 3: Add `PREFS_PATH` and `load_prefs` to `helpers.py`**

After the `DATA_PATH` line (line 35), add:

```python
PREFS_PATH = Path.home() / ".openclaw" / "dyk-prefs.json"
```

After the `save_store` function, add:

```python
def load_prefs() -> dict:
    """Load user tag preferences from PREFS_PATH.

    Returns {} if the file is missing (silently) or contains invalid JSON
    (warning to stderr).
    """
    try:
        text = PREFS_PATH.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"DYK: invalid prefs file ({PREFS_PATH}): {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        return {}
    return data
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_helpers.py::TestLoadPrefs -v
```

Expected: all 4 PASS.

**Step 5: Run full suite to check nothing is broken**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add scripts/helpers.py tests/test_helpers.py
git commit -m "feat: add load_prefs and PREFS_PATH to helpers"
```

---

### Task 2: `score_hook`

**Files:**
- Modify: `scripts/helpers.py`
- Modify: `tests/test_helpers.py`

---

**Step 1: Write the failing tests**

In `tests/test_helpers.py`, add a new `TestScoreHook` class after `TestLoadPrefs`:

```python
class TestScoreHook:
    def test_domain_preference_contributes_score(self):
        hook = {"tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}}
        prefs = {"domain": {"science": 1}, "tone": {}}
        assert helpers.score_hook(hook, prefs) == 1

    def test_negative_domain_preference_contributes_score(self):
        hook = {"tags": {"domain": ["military_history"], "tone": "straight", "low_confidence": False}}
        prefs = {"domain": {"military_history": -1}, "tone": {}}
        assert helpers.score_hook(hook, prefs) == -1

    def test_tone_preference_contributes_score(self):
        hook = {"tags": {"domain": ["history"], "tone": "surprising", "low_confidence": False}}
        prefs = {"domain": {}, "tone": {"surprising": 1}}
        assert helpers.score_hook(hook, prefs) == 1

    def test_both_dimensions_sum(self):
        hook = {"tags": {"domain": ["science"], "tone": "surprising", "low_confidence": False}}
        prefs = {"domain": {"science": 1}, "tone": {"surprising": 1}}
        assert helpers.score_hook(hook, prefs) == 2

    def test_untagged_hook_scores_zero(self):
        hook = {"text": "some fact", "urls": [], "returned": False, "tags": None}
        assert helpers.score_hook(hook, {"domain": {"science": 1}}) == 0

    def test_low_confidence_hook_scores_zero(self):
        hook = {"tags": {"domain": ["science"], "tone": "straight", "low_confidence": True}}
        prefs = {"domain": {"science": 1}, "tone": {}}
        assert helpers.score_hook(hook, prefs) == 0

    def test_tag_absent_from_prefs_defaults_to_zero(self):
        hook = {"tags": {"domain": ["animals"], "tone": "whimsical", "low_confidence": False}}
        assert helpers.score_hook(hook, {}) == 0

    def test_two_domain_tags_sum_their_scores(self):
        hook = {"tags": {"domain": ["science", "medicine_health"], "tone": "straight", "low_confidence": False}}
        prefs = {"domain": {"science": 1, "medicine_health": 1}, "tone": {}}
        assert helpers.score_hook(hook, prefs) == 2

    def test_two_domain_tags_mixed_scores(self):
        hook = {"tags": {"domain": ["science", "military_history"], "tone": "straight", "low_confidence": False}}
        prefs = {"domain": {"science": 1, "military_history": -1}, "tone": {}}
        assert helpers.score_hook(hook, prefs) == 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_helpers.py::TestScoreHook -v
```

Expected: all 9 FAIL — `AttributeError: module 'helpers' has no attribute 'score_hook'`

**Step 3: Add `score_hook` to `helpers.py`**

After `load_prefs`, add:

```python
def score_hook(hook: dict, prefs: dict) -> int:
    """Score a hook based on user preferences.

    Returns domain_score + tone_score.
    Untagged hooks (tags: None) and low-confidence hooks score 0.
    Domain score is the sum across all domain tags (1–2 tags).
    """
    tags = hook.get("tags")
    if not tags or tags.get("low_confidence"):
        return 0
    domain_prefs = prefs.get("domain") or {}
    tone_prefs = prefs.get("tone") or {}
    domain_tags = tags.get("domain") or []
    tone_tag = tags.get("tone")
    domain_score = sum((domain_prefs.get(tag) or 0) for tag in domain_tags)
    tone_score = (tone_prefs.get(tone_tag) or 0) if tone_tag else 0
    return domain_score + tone_score
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_helpers.py::TestScoreHook -v
```

Expected: all 9 PASS.

**Step 5: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add scripts/helpers.py tests/test_helpers.py
git commit -m "feat: add score_hook to helpers"
```

---

### Task 3: Update `next_hook` and `main` in `serve_hook.py`

**Files:**
- Modify: `scripts/serve_hook.py`
- Modify: `tests/test_serve_hook.py`

---

**Step 1: Write the failing tests**

In `tests/test_serve_hook.py`, add the following tests to the existing `TestNextHook` class:

```python
    def test_serves_highest_scored_hook_first(self):
        prefs = {"domain": {"science": 1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "history fact", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                        {"text": "science fact", "urls": [], "returned": False,
                         "tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "science fact" in result

    def test_tiebreak_most_recent_collection_first(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "fetched_at": "2026-02-23T12:00:00Z",
                 "hooks": [{"text": "older fact", "urls": [], "returned": False, "tags": None}]},
                {"date": "2026-02-24", "fetched_at": "2026-02-24T12:00:00Z",
                 "hooks": [{"text": "newer fact", "urls": [], "returned": False, "tags": None}]},
            ]
        }
        result = serve_hook.next_hook(store, {})
        assert "newer fact" in result

    def test_tiebreak_within_same_collection_is_random(self):
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "hook A", "urls": [], "returned": False, "tags": None},
                        {"text": "hook B", "urls": [], "returned": False, "tags": None},
                    ],
                }
            ]
        }
        seen = set()
        for _ in range(50):
            for h in store["collections"][0]["hooks"]:
                h["returned"] = False
            result = serve_hook.next_hook(store, {})
            seen.add("A" if "hook A" in result else "B")
        assert seen == {"A", "B"}

    def test_negative_scored_hooks_still_served(self):
        prefs = {"domain": {"history": -1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "history fact", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "history fact" in result

    def test_empty_prefs_serves_most_recent_first(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "fetched_at": "2026-02-23T12:00:00Z",
                 "hooks": [{"text": "old fact", "urls": [], "returned": False}]},
                {"date": "2026-02-24", "fetched_at": "2026-02-24T12:00:00Z",
                 "hooks": [{"text": "new fact", "urls": [], "returned": False}]},
            ]
        }
        result = serve_hook.next_hook(store, {})
        assert "new fact" in result
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_serve_hook.py::TestNextHook -v
```

Expected: the 5 new tests FAIL — `next_hook() takes 1 positional argument but 2 were given` (or similar). Existing 4 tests should still PASS.

**Step 3: Update `serve_hook.py`**

a) Add `import random` near the top (after `import sys`):

```python
import random
```

b) Add `load_prefs` and `score_hook` to the helpers import block (lines 12–21):

```python
from helpers import (
    collect_hooks,
    load_prefs,
    load_store,
    now_utc,
    save_store,
    score_hook,
    stored_urls,
    to_iso_z,
    trim_store,
    refresh_due,
)
```

c) Replace the entire `next_hook` function with:

```python
def next_hook(store: dict, prefs: dict | None = None) -> str:
    """Return the next unserved hook by score, or the exhausted message.

    Hooks are scored by domain + tone preference, served highest first.
    Ties broken by most recent collection, then randomly within a collection.
    """
    if prefs is None:
        prefs = {}
    collections = store.get("collections", [])
    candidates = []
    for coll_idx, coll in enumerate(reversed(collections)):
        for hook in coll.get("hooks", []):
            if not hook.get("returned"):
                candidates.append((score_hook(hook, prefs), coll_idx, hook))
    if not candidates:
        return "No more facts to share today; check back tomorrow!"
    # Sort: score descending, then most recent collection first (coll_idx=0 is newest)
    candidates.sort(key=lambda x: (-x[0], x[1]))
    top_score, top_coll_idx = candidates[0][0], candidates[0][1]
    tied = [c for c in candidates if c[0] == top_score and c[1] == top_coll_idx]
    hook = random.choice(tied)[2]
    hook["returned"] = True
    return format_hook(hook)
```

d) In `main()`, add `load_prefs()` call and pass to `next_hook`. Replace the last section of `main` (after `ensure_fresh`):

```python
    prefs = load_prefs()
    result = next_hook(store, prefs)
    save_store(store)
    print(result)
    return 0
```

**Step 4: Run the new tests to verify they pass**

```bash
pytest tests/test_serve_hook.py::TestNextHook -v
```

Expected: all 9 tests PASS (4 existing + 5 new).

**Step 5: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add scripts/serve_hook.py tests/test_serve_hook.py
git commit -m "feat: serve hooks by preference score"
```

---

### Task 4: Template prefs file and backwards-compat TODO

**Files:**
- Create: `tagging/dyk-prefs.json`
- Modify: `tests/test_dyk.py`

---

**Step 1: Create the template prefs file**

Create `tagging/dyk-prefs.json`:

```json
{
  "domain": {
    "history": 0,
    "military_history": 0,
    "science": 0,
    "medicine_health": 0,
    "technology": 0,
    "economics_business": 0,
    "sports": 0,
    "music": 0,
    "film": 0,
    "television": 0,
    "journalism": 0,
    "literature": 0,
    "visual_art": 0,
    "performing_arts": 0,
    "places": 0,
    "animals": 0,
    "nature": 0,
    "religion": 0,
    "mythology_folklore": 0,
    "language_linguistics": 0
  },
  "tone": {
    "straight": 0,
    "surprising": 0,
    "quirky": 0,
    "whimsical": 0,
    "dark": 0,
    "inspiring": 0,
    "poignant": 0,
    "dramatic": 0,
    "provocative": 0
  }
}
```

**Step 2: Add the TODO comment to `test_dyk.py`**

In `tests/test_dyk.py`, add a comment inside the `TestBackwardsCompatibility` class docstring area. After the class docstring, add:

```python
    # TODO: add backwards-compat tests pinning PREFS_PATH location
    #       (~/.openclaw/dyk-prefs.json) and ensuring that a missing prefs
    #       file serves hooks with neutral scoring (score 0).
```

**Step 3: Run full suite to confirm nothing broke**

```bash
pytest -v
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add tagging/dyk-prefs.json tests/test_dyk.py
git commit -m "feat: add template prefs file and backwards-compat TODO"
```
