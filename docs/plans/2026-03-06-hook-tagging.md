# DYK Hook Tagging System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce `tagging/tags.csv` (controlled vocabulary) and `tagging/tagged_sample.jsonl` (100 annotated hooks) to support future user preference modeling and ML recommendation.

**Architecture:** Collaborative corpus-first approach — first sample and analyze hooks to discover natural clusters, then name those clusters with the user, then use the Claude API to tag the full sample against the resulting vocabulary.

**Tech Stack:** Python 3, `anthropic` SDK, `jsonlines` (or stdlib json), pytest

---

### Task 1: Sample extraction script

Randomly sample 100 hooks from the archive and print them cleanly for manual analysis.

**Files:**
- Create: `tagging/sample_hooks.py`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Randomly sample N hooks from archive_hooks.jsonl and print for analysis."""
import json, random, sys
from pathlib import Path

ARCHIVE = Path(__file__).parent.parent / "tools" / "archive_hooks.jsonl"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42

hooks = [json.loads(line) for line in ARCHIVE.read_text().splitlines() if line.strip()]
random.seed(SEED)
sample = random.sample(hooks, N)

for i, h in enumerate(sample, 1):
    print(f"{i:03d}. {h['raw']}")
    print()
```

**Step 2: Run it**

```bash
python3 tagging/sample_hooks.py 100 42
```

Expected: 100 hooks printed, numbered 001–100.

**Step 3: Save output to file for analysis**

```bash
python3 tagging/sample_hooks.py 100 42 > tagging/sample_100.txt
```

---

### Task 2: Collaborative corpus analysis (in-session)

**This task is conversational, not code.**

Hand the `tagging/sample_100.txt` output to Claude in the current session and ask it to:

1. Read all 100 hooks
2. Group them into natural clusters by subject matter, emotional register, and structural pattern
3. Report the clusters WITHOUT naming them — just describe what's in each group
4. Note which clusters are large enough to warrant a tag (appear in 5+ hooks)

Do not proceed to Task 3 until the user has reviewed the cluster report.

---

### Task 3: Vocabulary definition (collaborative, in-session)

**This task is conversational, not code.**

Working from the cluster report:

1. Name each cluster (becomes a `tag_id`)
2. Assign it a dimension: `domain`, `tone`, or `style`
3. Write a one-sentence description for each tag

Output: the contents of `tagging/tags.csv`.

---

### Task 4: Create tags.csv

Once vocabulary is agreed, write the file.

**Files:**
- Create: `tagging/tags.csv`

**Step 1: Write the file** with agreed tags in this format:

```csv
tag_id,dimension,description
science,domain,Natural sciences including physics biology chemistry astronomy etc.
history,domain,Historical events figures and periods
...
quirky,tone,Funny odd or unexpectedly absurd
dark,tone,Involving death tragedy or suffering
...
record_breaking,style,Hook centres on a superlative or a first/last achievement
unexpected_connection,style,Two unrelated things turn out to be linked
...
```

**Step 2: Validate** — count rows, confirm each dimension has at least 3 tags:

```bash
python3 -c "
import csv
rows = list(csv.DictReader(open('tagging/tags.csv')))
by_dim = {}
for r in rows:
    by_dim.setdefault(r['dimension'], []).append(r['tag_id'])
for dim, tags in sorted(by_dim.items()):
    print(f'{dim} ({len(tags)}): {tags}')
"
```

---

### Task 5: Tagging script using Claude API

Write a script that reads each hook from the sample, calls Claude to assign tags from the vocabulary, and writes `tagging/tagged_sample.jsonl`.

**Files:**
- Create: `tagging/tag_hooks.py`
- Read: `tagging/tags.csv` (vocabulary)
- Read: `tagging/sample_100.txt` (hook list) — actually re-derive from archive with same seed
- Write: `tagging/tagged_sample.jsonl`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Tag a sample of hooks using Claude API against a controlled vocabulary."""
import anthropic, csv, json, random, sys, textwrap
from pathlib import Path

ARCHIVE = Path(__file__).parent.parent / "tools" / "archive_hooks.jsonl"
TAGS_CSV = Path(__file__).parent / "tags.csv"
OUTPUT = Path(__file__).parent / "tagged_sample.jsonl"
N = 100
SEED = 42
MODEL = "claude-haiku-4-5-20251001"  # cheapest capable model

# Load vocabulary
tags = list(csv.DictReader(TAGS_CSV.open()))
by_dim = {}
for t in tags:
    by_dim.setdefault(t["dimension"], []).append(t["tag_id"])

vocab_block = "\n".join(
    f"{dim}: {', '.join(tag_ids)}" for dim, tag_ids in sorted(by_dim.items())
)

# Sample hooks
hooks = [json.loads(l) for l in ARCHIVE.read_text().splitlines() if l.strip()]
random.seed(SEED)
sample = random.sample(hooks, N)

client = anthropic.Anthropic()

def tag_hook(raw: str) -> dict:
    prompt = textwrap.dedent(f"""
        You are tagging Wikipedia "Did You Know?" hooks with a controlled vocabulary.

        Vocabulary:
        {vocab_block}

        Rules:
        - domain: choose 1–2 tags
        - tone: choose exactly 1 tag
        - style: choose exactly 1 tag
        - Only use tags from the vocabulary above. Never invent new tags.
        - Respond with JSON only, no explanation.

        Hook: {raw}

        Respond with:
        {{"domain": ["tag"], "tone": "tag", "style": "tag"}}
    """).strip()

    msg = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(msg.content[0].text)

results = []
for i, hook in enumerate(sample, 1):
    print(f"Tagging {i}/{N}...", end="\r", flush=True)
    tags_assigned = tag_hook(hook["raw"])
    results.append({"raw": hook["raw"], **tags_assigned})

print()
OUTPUT.write_text("\n".join(json.dumps(r) for r in results) + "\n")
print(f"Wrote {len(results)} tagged hooks to {OUTPUT}")
```

**Step 2: Run it**

```bash
python3 tagging/tag_hooks.py
```

Expected: progress counter, then "Wrote 100 tagged hooks to tagging/tagged_sample.jsonl"

**Step 3: Spot-check output**

```bash
python3 -c "
import json
hooks = [json.loads(l) for l in open('tagging/tagged_sample.jsonl')]
print(f'Total: {len(hooks)}')
for h in hooks[:5]:
    print(h)
"
```

---

### Task 6: Validate tag distribution

Check that the tags are being used sensibly — no dimension has a single tag dominating.

**Step 1: Run distribution check**

```python
# Run inline
import json, collections

hooks = [json.loads(l) for l in open("tagging/tagged_sample.jsonl")]

domain_counts = collections.Counter()
tone_counts = collections.Counter()
style_counts = collections.Counter()

for h in hooks:
    for d in h.get("domain", []):
        domain_counts[d] += 1
    tone_counts[h.get("tone", "?")] += 1
    style_counts[h.get("style", "?")] += 1

print("DOMAIN:", domain_counts.most_common())
print("TONE:  ", tone_counts.most_common())
print("STYLE: ", style_counts.most_common())
```

```bash
python3 -c "
import json, collections
hooks = [json.loads(l) for l in open('tagging/tagged_sample.jsonl')]
dc, tc, sc = collections.Counter(), collections.Counter(), collections.Counter()
for h in hooks:
    for d in h.get('domain', []): dc[d] += 1
    tc[h.get('tone','?')] += 1
    sc[h.get('style','?')] += 1
print('DOMAIN:', dc.most_common())
print('TONE:  ', tc.most_common())
print('STYLE: ', sc.most_common())
"
```

Expected: reasonable spread. Flag to user if any single tag covers >50% of hooks.

**Step 2: Human spot-check** — user reviews 10–15 random tagged hooks and notes any misfits.

---

### Task 7: Iterate vocabulary if needed

If spot-check reveals problems (wrong tags, missing tags, over-broad tags):

1. Edit `tagging/tags.csv` to fix vocabulary
2. Re-run `python3 tagging/tag_hooks.py` to regenerate `tagged_sample.jsonl`
3. Re-run distribution check

Repeat until distribution looks healthy.

---

## Out of Scope

- Integration into `dyk.py`
- Full corpus tagging (118k hooks)
- User preference storage or serving hooks by category
- ML model training
