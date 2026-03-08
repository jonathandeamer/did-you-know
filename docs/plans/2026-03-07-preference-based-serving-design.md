# Preference-Based Hook Serving — Design

## Goal

Serve hooks ordered by user-declared tag preferences rather than arrival order alone.

## Data model

**`~/.openclaw/dyk-prefs.json`** — manually edited by the user, read each run:

```json
{
  "domain": { "science": 1, "military_history": -1, "history": 0 },
  "tone":   { "surprising": 1, "dark": -1 }
}
```

- Valid scores: `1` (prefer), `0` (neutral), `-1` (avoid)
- Missing file → `{}` silently (all scores 0 — current behaviour preserved)
- Invalid JSON → `{}` and print warning to stderr
- Missing or `null` score for any tag → `0`
- Out-of-range values are used as-is; only `1`, `0`, `-1` are documented as valid

A **template file** (`tagging/dyk-prefs.json`) with all scores set to `0` is committed to the repo so users have a copy-editable reference.

## Scoring

```
hook_score = domain_score + tone_score
```

- **Untagged hooks** (`tags: null`): score = `0`, eligible
- **Low-confidence hooks** (`low_confidence: true`): score = `0`, eligible (tags ignored)
- **Domain score**: sum of prefs scores for all domain tags on the hook (1–2 tags → range −2 to +2)
- **Tone score**: pref score for the single tone tag (range −1 to +1)
- **Total range**: −3 to +3

Hooks are always served — negative scores are never withheld.

## Tiebreaking

1. Score descending
2. Most recently fetched collection first
3. Random selection among hooks with identical score from the same collection

## Architecture

**`helpers.py`** — two additions:

- `PREFS_PATH = Path.home() / ".openclaw" / "dyk-prefs.json"`
- `load_prefs() -> dict` — reads `PREFS_PATH`, returns `{}` on missing file (silently) or invalid JSON (warning to stderr)
- `score_hook(hook: dict, prefs: dict) -> int` — pure scoring function

**`serve_hook.py`** — one change:

- `next_hook(store, prefs)` gains a `prefs` parameter; gathers all unreturned hooks, scores them, applies tiebreaking, serves the top candidate
- `main()` calls `load_prefs()` and passes the result to `next_hook`

## Testing

**New `TestScoreHook` in `test_helpers.py`:**
- Matching domain preference contributes correct score
- Matching tone preference contributes correct score
- Both dimensions sum correctly
- `tags: null` → score 0
- `low_confidence: true` → score 0 (tags ignored)
- Tag absent from prefs → 0
- Two domain tags sum their individual scores

**New `TestLoadPrefs` in `test_helpers.py`:**
- Missing file → `{}`
- Invalid JSON → `{}` and warning printed to stderr

**Updated `TestNextHook` in `test_serve_hook.py`:**
- Highest-scored hook served first
- Tiebreak: most recent collection first
- Tiebreak within same collection: random (verified probabilistically)
- Negative-scored hooks still served when nothing better exists
- Untagged hooks (score 0) served when all scores equal
- Empty prefs (`{}`) preserves existing behaviour

## Backwards compatibility

Existing `TestBackwardsCompatibility` tests pass unchanged (missing prefs file → `{}` → neutral scoring). A `# TODO` comment is added to `test_dyk.py` noting that future tests should pin `PREFS_PATH` and the no-prefs-file contract explicitly.
