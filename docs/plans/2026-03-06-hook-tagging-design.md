# DYK Hook Tagging System — Design

## Purpose

Enable user preference modeling and a future ML recommender by tagging hooks with a
controlled vocabulary. Users will eventually be able to express preferences
(e.g. "I prefer science, skip sports"), and a downstream model will use tag
co-occurrence with engagement signals to recommend hooks.

## Dimensions

Two dimensions only:

| Dimension | Per-hook limit | Description |
|-----------|---------------|-------------|
| `domain`  | 1–2 tags      | What field or subject area the hook is about |
| `tone`    | 1 tag         | The emotional register of the hook |
| `style`   | 1 tag         | The structural pattern of the hook |

Whether `tone` and `style` remain separate or merge into a single dimension is
determined during corpus analysis.

## Phased Approach

### Phase 1 — Corpus Analysis

Read a random 100-hook sample from `tools/archive_hooks.jsonl`. Produce a raw
thematic analysis — observed clusters of subject matter, emotional register, and
structural hook patterns — with no tags assigned yet. Collaborate to name the
clusters and define the vocabulary.

### Phase 2 — Vocabulary

Produce `tagging/tags.csv` with columns:

```
tag_id,dimension,description
science,domain,Natural sciences including physics, biology, chemistry, etc.
quirky,tone,Funny, odd, or unexpectedly absurd
record_breaking,style,Hook centres on a superlative or first/last achievement
```

Target size: ~30–60 tags total across all dimensions.

### Phase 3 — Tagged Sample

Produce `tagging/tagged_sample.jsonl` — 100 hooks annotated using the vocabulary:

```json
{"raw": "...", "domain": ["science"], "tone": "quirky", "style": "unexpected_connection"}
```

This becomes the gold set for future LLM tagging of the full corpus and ML feature
engineering.

## Out of Scope (for now)

- Integration into `dyk.py`
- Serving hooks by category
- User preference storage
- Full corpus tagging
- ML model training
