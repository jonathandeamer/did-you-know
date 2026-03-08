# Prefs CLI Design

## Goal

A deterministic command-line interface for reading and writing `dyk-prefs.json`, intended for use by an LLM managing user preferences based on hook reactions.

## Why a CLI rather than direct JSON editing

Direct JSON editing by an LLM is fragile. A dedicated CLI allows us to enshrine validation rules and guardrails: unknown tags are rejected, values are constrained to a fixed vocabulary, and the file is written atomically. The LLM calls commands; it never touches the JSON itself.

## Commands

```
prefs.py init
prefs.py list
prefs.py get <dimension> <tag>
prefs.py set <dimension> <tag> <like|neutral|dislike>
```

## Value vocabulary

| Word | Stored value |
|---|---|
| `like` | `1` |
| `neutral` | `0` |
| `dislike` | `-1` |

Words rather than numbers prevent an LLM from passing out-of-range values by accident.

## Validation

- Dimension must be known (loaded from `tags.csv`)
- Tag must exist within that dimension
- Value must be one of `like`, `neutral`, `dislike`

Vocabulary is loaded from the same `tags.csv` used by `write_tags.py`, so the CLI stays in sync automatically as new dimensions/tags are added.

## Behaviour

**`init`** — if `dyk-prefs.json` already exists, print a message and exit 1. Otherwise write the full prefs structure (all values `0`) to `PREFS_PATH` and exit 0.

**`list`** — pretty-print current prefs grouped by dimension. Suggests `init` if file is missing.

**`get`** — print the word (`like`/`neutral`/`dislike`) for the given dimension/tag. Suggests `init` if file is missing.

**`set`** — validate dimension/tag/value, update the single value, save atomically using the same write-to-temp-then-rename pattern as `helpers.save_store`. Print confirmation.

## Error handling

All validation failures and missing-file conditions exit 1 with a clear message. No silent failures.

## File location

`scripts/prefs.py` — consistent with `fetch_hooks.py`, `write_tags.py`, `serve_hook.py`.
