# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**did-you-know** (dyk) is an **OpenClaw skill** implemented in Python that fetches English Wikipedia's "Did You Know?" facts, caches them locally, and serves them one at a time. It extracts well-sourced facts from the DYK template without requiring an API key and does not modify Wikipedia.

This skill is registered as an OpenClaw command that users can invoke to get conversation starters from Wikipedia's curated collection of interesting facts.

## Quick Start

### Run the script
```bash
python3 scripts/dyk.py
```

Output on success:
```
Did you know that [fact]?

[URL1]
[URL2]
```

Output when no new facts available:
```
No more facts to share today; check back tomorrow!
```

### Run tests
```bash
python3 -m pytest tests/ -v
```

Run a specific test:
```bash
python3 -m pytest tests/test_helpers.py::TestNormalizeText -v
```

## OpenClaw Skill Metadata

This repository is an OpenClaw skill. See `SKILL.md` for:
- Skill registration metadata (name, description, homepage)
- How the skill is exposed to users
- OpenClaw-specific configuration

The entry point `scripts/dyk.py` is a thin shim that delegates to `scripts/serve_hook.py`. Both can be invoked directly from the command line.

## Architecture

### Scripts

- **`scripts/helpers.py`** — Shared utilities: text parsing, MediaWiki API, cache management, timestamps. No I/O side effects at import time.
- **`scripts/serve_hook.py`** — Refresh and serving logic (`ensure_fresh`, `next_hook`, `main`). Imports from `helpers`.
- **`scripts/dyk.py`** — Backwards-compatible shim; re-exports `main` from `serve_hook`.
- **`scripts/fetch_hooks.py`** — Standalone script for pre-fetching hooks into the cache (used by cron/automation).
- **`scripts/write_tags.py`** — Applies subject/tone tags from a JSON file into the cache.

### Main Components

1. **Text Parsing & Normalization** (`helpers.py`)
   - `normalize_text()`: Strips Wikipedia markup (wikilinks, templates, bold/italic), handles special cases like possessive markers and "pictured" parentheticals
   - `extract_hook_titles()`: Extracts article titles from wikitext, preferring bold-linked titles
   - `extract_hooks_section()`: Isolates the hooks section between `<!--Hooks-->` and `<!--HooksEnd-->` markers

2. **MediaWiki API Integration** (`helpers.py`)
   - `fetch_wikitext()`: Fetches the DYK template from Wikipedia API with automatic retry/backoff
   - `collect_hooks()`: Parses wikitext to extract individual hooks, dedupes URLs by normalizing to unquoted form for comparison against cache history, returns list of hook objects

3. **Local Cache Management** (`helpers.py`)
   - Cache stored in `~/.openclaw/dyk-facts.json`
   - `load_store()`: Loads JSON cache (gracefully handles missing/corrupted files)
   - `save_store()`: Persists cache to disk with UTF-8 encoding
   - `trim_store()`: Drops collections fetched 8 or more days ago (configurable via `MAX_HOOK_AGE_DAYS`)

4. **Refresh & Serving Logic** (`serve_hook.py`)
   - `ensure_fresh()`: Checks if refresh needed (every 12-24 hours via `REFRESH_INTERVAL`), fetches new hooks if needed, skips appending empty collections
   - `next_hook(store, prefs)`: Scores all unreturned hooks and serves the highest-scoring one. Priority: score desc → newest collection → shortest text → random. Writes `returned_at` to the served hook.
   - `refresh_due()`: Determines if cache refresh is needed based on timestamp

5. **Preference-Based Scoring** (`helpers.py`)
   - `load_prefs()`: Reads `PREFS_PATH` (`~/.openclaw/dyk-prefs.json`); returns `{}` silently if missing, warns to stderr on invalid JSON
   - `score_hook(hook, prefs, freshness_bonus, prev_domains)`: Composite scoring function — see its docstring for the full model (domain/tone preferences, diversity penalty, freshness, multi-link, brevity bonuses)
   - `last_served_domains(store)`: Returns domain tags of the most recently served hook (identified via `returned_at` timestamps), used to apply the diversity penalty

6. **Utility Functions** (`helpers.py`)
   - `title_to_url()`: Converts article titles to Wikipedia URLs with proper URL encoding
   - `retry_with_backoff()`: Generic exponential backoff retry wrapper
   - `now_utc()`, `to_iso_z()`, `parse_iso()`: ISO 8601 timestamp helpers

### Data Structure

Cache format (stored at `DATA_PATH`):
```json
{
  "seen_urls": [
    "https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"
  ],
  "last_checked_at": "2026-02-24T12:00:00Z",
  "collections": [
    {
      "date": "2026-02-24",
      "fetched_at": "2026-02-24T12:00:00Z",
      "hooks": [
        {
          "text": "normalized fact text",
          "urls": ["https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"],
          "tags": {"domain": ["science"], "tone": "surprising", "low_confidence": false},
          "returned": true,
          "returned_at": "2026-02-24T14:00:00Z"
        }
      ]
    }
  ]
}
```

`tags` is `null` for hooks that have not yet been tagged by `write_tags.py`. `returned_at` is written when a hook is served and is used to identify the previously served domain for the diversity penalty.

## Key Design Decisions

- **No API key required**: Uses public MediaWiki API
- **Deduplication across history**: Tracks all previously served URLs to avoid repeating facts
- **Graceful degradation**: Uses cached facts if network fetch fails
- **Stale refresh check**: If new facts are all duplicates, refresh flag stays True (re-checks on next run)
- **URL encoding/decoding**: URLs are stored encoded but decoded for display to match Wikipedia's presentation
- **Preference-based serving**: Hooks are scored and served by priority using user-declared tag preferences (`~/.openclaw/dyk-prefs.json`), with bonuses for freshness, brevity, and multiple sources, and a diversity penalty for consecutive same-domain hooks. Missing prefs file → neutral scoring (existing behaviour preserved).

## Development Philosophy

### Test-Driven Development
Always follow red-green TDD where possible:
1. Write a failing test that captures the required behaviour (red)
2. Write the minimum implementation to make it pass (green)
3. Refactor if needed, keeping tests green

Do not write implementation code before a failing test exists for it.

### Dependencies
Do not introduce dependencies outside the Python standard library unless absolutely essential. If a third-party package seems necessary, raise it for discussion first before adding it.

## Testing

Tests use pytest with monkeypatching for dependencies:
- Mocks `urllib.request.urlopen` for API responses
- Mocks `time.sleep` to skip delays in retry tests
- Uses `tmp_path` fixture for file I/O tests

Test files by module:
- `tests/test_helpers.py` — text parsing, API fetching, cache management (`helpers.py`)
- `tests/test_serve_hook.py` — refresh logic, serving, main flow (`serve_hook.py`)
- `tests/test_dyk.py` — backwards-compatibility contract (stdout format, exit codes, cache schema)
- `tests/test_fetch_hooks.py` — pre-fetch script (`fetch_hooks.py`)
- `tests/test_write_tags.py` — tag application script (`write_tags.py`)

Key test patterns:
- Individual parser functions tested with regex edge cases
- API retry logic tested with configurable retry/backoff parameters
- Store operations tested with missing/corrupted files
- Main flow tested with network failures using fallback logic

## File Tracking & Release Packaging

### .gitignore — deny-all whitelist
`.gitignore` uses a `*` deny-all pattern: **every new file must be explicitly whitelisted** with a `!` entry or git will ignore it. When adding a new tracked file, add it to `.gitignore` first.

### .gitattributes — release archive trimming
GitHub release archives (zip/tarball) should contain only what a user needs to run the skill: `SKILL.md`, `scripts/`, and `tagging/`. Development scaffolding is stripped via `export-ignore`:
- Always `export-ignore`: `.gitattributes`, `.gitignore`, `.gitmessage`, `.githooks/`, `CONTRIBUTING.md`, `pyproject.toml`, `tests/`
- Never `export-ignore`: `SKILL.md`, `scripts/*.py`, `tagging/`

When adding a new file, decide which category it belongs to and update `.gitattributes` accordingly. If unsure whether a file should be tracked or export-ignored, ask before acting.

## Commit Convention

This project uses Conventional Commits. Use these types:
- `feat`: New functionality
- `fix`: Bug fixes
- `docs`: Documentation updates
- `test`: Test additions/changes
- `refactor`: Code structure improvements (no behavior change)
- `perf`: Performance improvements
- `chore`: Maintenance, dependencies
- `style`: Code style (linting, formatting)

Examples:
```
feat: add URL deduplication across collections
fix(parser): handle escaped apostrophes in wikitext
docs: clarify cache structure in README
```

## Important Files

- `scripts/helpers.py`: Shared utilities (parsing, caching, API, timestamps)
- `scripts/serve_hook.py`: Refresh and serving logic; entry point for `main()`
- `scripts/dyk.py`: Backwards-compatible shim — delegates to `serve_hook.main()`
- `tests/test_helpers.py`: Unit tests for `helpers.py`
- `tests/test_serve_hook.py`: Unit tests for `serve_hook.py`
- `tests/test_dyk.py`: Backwards-compatibility contract tests
- `.gitmessage`: Conventional commit template

## Constants & Configuration

- `helpers.py`: `API_URL`, `DATA_PATH`, `PREFS_PATH`, `MAX_HOOK_AGE_DAYS`, `REFRESH_INTERVAL`, `CHECK_COOLDOWN`, regex patterns (`RE_HOOK_LINE`, `RE_LINK`, `RE_BOLD_SECTION`), timestamp helpers
- `serve_hook.py`: `MSG_PREFIX`, `MSG_SUFFIX`, `MSG_URL_SEPARATOR`, `MSG_BODY_SEPARATOR`

## Common Development Tasks

### Add a new parser function
1. Add regex pattern or helper at top of `helpers.py` with other `RE_*` constants
2. Implement function with clear docstring
3. Add tests in `TestXxx` class in `tests/test_helpers.py`
4. Test with `pytest tests/test_helpers.py::TestXxx -v`

### Modify cache schema
1. Ensure backward compatibility (load_store handles old format gracefully)
2. Update data structure tests in `TestStoreHelpers`
3. Consider migration path for existing caches

### Debug a specific hook
Add temporary code in `main()` to inspect `store` structure after `ensure_fresh()` call, or use a Python REPL with `scripts/dyk.py` in `sys.path`.
